package state

import (
	"path/filepath"
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
	root := RunsRoot()
	w, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, err
	}
	wr := &Watcher{
		w:      w,
		events: make(chan WatchEvent, 64),
		stop:   make(chan struct{}),
	}
	// Watch the root and every existing run subdir. New subdirs are added
	// dynamically when we see Create events for them.
	_ = w.Add(root)
	if entries, err := readDirSafe(root); err == nil {
		for _, name := range entries {
			_ = w.Add(filepath.Join(root, name))
		}
	}
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
			// Add new subdirs to the watch list so manifest.json writes
			// inside them are observed.
			if ev.Op&fsnotify.Create != 0 {
				if info, err := osStat(ev.Name); err == nil && info.IsDir() {
					_ = wr.w.Add(ev.Name)
				}
			}
			select {
			case wr.events <- WatchEvent{Path: ev.Name, Op: ev.Op}:
			case <-wr.stop:
				return
			case <-time.After(50 * time.Millisecond):
				// drop the event if nobody's listening; the TUI re-reads
				// on every render tick anyway.
			}
		case _, ok := <-wr.w.Errors:
			if !ok {
				return
			}
		}
	}
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
