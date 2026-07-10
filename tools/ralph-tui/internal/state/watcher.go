package state

import (
	"errors"
	"io/fs"
	"path/filepath"
	"strings"
	"time"

	"github.com/fsnotify/fsnotify"
)

// WatchEvent is emitted whenever a file under RunsRoot changes (added,
// modified, removed). Subscribers re-load only what they need.
type WatchEvent struct {
	Path string
	Op   fsnotify.Op
}

// Watcher streams filesystem events under RunsRoot. Closing it stops the
// goroutine and closes the events channel.
type Watcher struct {
	w      *fsnotify.Watcher
	events chan WatchEvent
	stop   chan struct{}
	root   string
}

// NewWatcher recursively watches RunsRoot for create/modify/remove events.
//
// The TUI uses the resulting events to invalidate caches: a manifest.json
// change for a known run id triggers a re-read of that single run; a
// directory creation/deletion triggers a full LoadRuns().
//
// Debouncing is the caller's responsibility: a burst of writes during a
// manifest save can produce 2-3 events for one logical change.
func NewWatcher() (*Watcher, error) {
	w, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, err
	}
	wr := &Watcher{
		w:      w,
		events: make(chan WatchEvent, 64),
		stop:   make(chan struct{}),
		root:   filepath.Clean(RunsRoot()),
	}
	wr.syncWatches()
	go wr.loop()
	return wr, nil
}

// Events returns the read end of the watch channel.
func (wr *Watcher) Events() <-chan WatchEvent { return wr.events }

// Close stops the watcher.
func (wr *Watcher) Close() error {
	select {
	case <-wr.stop:
		return nil
	default:
		close(wr.stop)
	}
	return wr.w.Close()
}

func (wr *Watcher) loop() {
	defer close(wr.events)
	for {
		select {
		case <-wr.stop:
			return
		case ev, ok := <-wr.w.Events:
			if !ok {
				return
			}
			var synthetic []WatchEvent
			if ev.Op&fsnotify.Create != 0 {
				if info, err := osStat(ev.Name); err == nil && info.IsDir() {
					for _, dir := range wr.syncWatches() {
						if filepath.Clean(dir) == filepath.Clean(ev.Name) {
							continue
						}
						synthetic = append(synthetic, WatchEvent{Path: dir, Op: fsnotify.Create})
					}
				}
			}
			if wr.isUnderRoot(ev.Name) {
				if !wr.emit(WatchEvent{Path: ev.Name, Op: ev.Op}) {
					return
				}
			}
			for _, sev := range synthetic {
				if !wr.emit(sev) {
					return
				}
			}
		case _, ok := <-wr.w.Errors:
			if !ok {
				return
			}
		}
	}
}

func (wr *Watcher) syncWatches() []string {
	var added []string
	if path := deepestExistingDir(wr.root); path != "" {
		_, _ = wr.addWatch(path)
	}
	if !isDir(wr.root) {
		return added
	}
	_, _ = wr.addWatch(wr.root)
	if entries, err := readDirSafe(wr.root); err == nil {
		for _, name := range entries {
			path := filepath.Join(wr.root, name)
			if !isDir(path) {
				continue
			}
			if ok, _ := wr.addWatch(path); ok {
				added = append(added, path)
			}
		}
	}
	return added
}

func (wr *Watcher) addWatch(path string) (bool, error) {
	path = filepath.Clean(path)
	if wr.hasWatch(path) {
		return false, nil
	}
	if err := wr.w.Add(path); err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

func (wr *Watcher) hasWatch(path string) bool {
	for _, watched := range wr.w.WatchList() {
		if filepath.Clean(watched) == path {
			return true
		}
	}
	return false
}

func (wr *Watcher) isUnderRoot(path string) bool {
	path = filepath.Clean(path)
	if path == wr.root {
		return true
	}
	return strings.HasPrefix(path, wr.root+string(filepath.Separator))
}

func (wr *Watcher) emit(ev WatchEvent) bool {
	select {
	case wr.events <- ev:
		return true
	case <-wr.stop:
		return false
	case <-time.After(50 * time.Millisecond):
		// drop the event if nobody's listening; the TUI re-reads
		// on every render tick anyway.
		return true
	}
}

func deepestExistingDir(path string) string {
	path = filepath.Clean(path)
	for {
		if isDir(path) {
			return path
		}
		parent := filepath.Dir(path)
		if parent == path {
			return ""
		}
		path = parent
	}
}

func isDir(path string) bool {
	info, err := osStat(path)
	return err == nil && info.IsDir()
}

// osStat is split out so tests can stub the filesystem if needed; on real
// runs it just delegates to os.Stat. Using a package-level var keeps
// readDirSafe out of the production path's hot loop.
var osStat = func(name string) (osFileInfo, error) {
	return statShim(name)
}

type osFileInfo interface {
	IsDir() bool
}
