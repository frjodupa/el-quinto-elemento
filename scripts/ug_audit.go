package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/Pilfer/ultimate-guitar-scraper/pkg/ultimateguitar"
)

func main() {
	mode := flag.String("mode", "search", "search or fetch")
	query := flag.String("query", "", "song title / query")
	id := flag.Int64("id", 0, "tab id")
	flag.Parse()

	s := ultimateguitar.New()

	switch *mode {
	case "search":
		if *query == "" {
			fmt.Fprintln(os.Stderr, "missing -query")
			os.Exit(2)
		}
		res, err := s.Search(ultimateguitar.SearchParams{
			Title: *query,
			Type:  []ultimateguitar.TabType{ultimateguitar.TabTypeChords},
			Page:  1,
		})
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if err := json.NewEncoder(os.Stdout).Encode(res); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "fetch":
		if *id <= 0 {
			fmt.Fprintln(os.Stderr, "missing -id")
			os.Exit(2)
		}
		tab, err := s.GetTabByID(*id)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if err := json.NewEncoder(os.Stdout).Encode(tab); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	default:
		fmt.Fprintln(os.Stderr, "unknown mode")
		os.Exit(2)
	}
}
