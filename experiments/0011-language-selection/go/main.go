// Disposable #0011 header-walk comparison; not a production CR3 parser.
package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"os"
)

func scan(r io.ReadSeeker, length int64, budget int) (int, error) {
	var offset int64
	count := 0
	bad := errors.New("invalid or limited header")
	for offset < length {
		if count == budget || length-offset < 8 {
			return 0, bad
		}
		if _, err := r.Seek(offset, io.SeekStart); err != nil {
			return 0, err
		}
		var h [8]byte
		if _, err := io.ReadFull(r, h[:]); err != nil {
			return 0, err
		}
		short := binary.BigEndian.Uint32(h[:4])
		size, min := uint64(short), uint64(8)
		if short == 0 {
			size = uint64(length - offset)
		}
		if short == 1 {
			if length-offset < 16 {
				return 0, bad
			}
			if _, err := io.ReadFull(r, h[:]); err != nil {
				return 0, err
			}
			size, min = binary.BigEndian.Uint64(h[:]), 16
		}
		if size < min || size > uint64(length-offset) {
			return 0, bad
		}
		offset += int64(size)
		count++
	}
	return count, nil
}
func main() {
	bad := [][]byte{{0, 0, 0, 0, 0, 0, 0}, {0, 0, 0, 4, 'f', 'r', 'e', 'e'}, {0, 0, 0, 20, 'f', 'r', 'e', 'e'}, {0, 0, 0, 1, 'f', 'r', 'e', 'e', 255, 255, 255, 255, 255, 255, 255, 255}}
	for _, b := range bad {
		if _, e := scan(bytes.NewReader(b), int64(len(b)), 32); e == nil {
			panic("invalid accepted")
		}
	}
	valid := []byte{0, 0, 0, 8, 'f', 'r', 'e', 'e'}
	if n, e := scan(bytes.NewReader(valid), 8, 1); e != nil || n != 1 {
		panic("valid rejected")
	}
	if _, e := scan(bytes.NewReader(valid), 8, 0); e == nil {
		panic("budget ignored")
	}
	counts := []int{}
	for _, path := range os.Args[1:] {
		f, e := os.Open(path)
		if e != nil {
			panic(e)
		}
		st, e := f.Stat()
		if e != nil {
			panic(e)
		}
		n, e := scan(f, st.Size(), 4096)
		f.Close()
		if e != nil {
			panic(e)
		}
		counts = append(counts, n)
	}
	json.NewEncoder(os.Stdout).Encode(map[string]any{"header_cases": 6, "private_inputs": len(counts), "private_top_level_box_counts": counts, "production_capabilities": 0})
}
