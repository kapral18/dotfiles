package state

import (
	"errors"
	"io/fs"
	"os"
)

// readDirSafe returns directory entries, ignoring "not exist" errors.
func readDirSafe(path string) ([]string, error) {
	entries, err := os.ReadDir(path)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil, nil
		}
		return nil, err
	}
	out := make([]string, 0, len(entries))
	for _, e := range entries {
		out = append(out, e.Name())
	}
	return out, nil
}

// statShim wraps os.Stat with the watcher's narrow interface.
func statShim(name string) (osFileInfo, error) {
	info, err := os.Stat(name)
	if err != nil {
		return nil, err
	}
	return statWrapper{info}, nil
}

type statWrapper struct{ info os.FileInfo }

func (s statWrapper) IsDir() bool { return s.info.IsDir() }
