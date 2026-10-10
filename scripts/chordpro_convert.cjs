const fs = require("fs");
const ChordSheetJS = require("chordsheetjs");

const input = JSON.parse(fs.readFileSync(0, "utf8"));
const parser = new ChordSheetJS.ChordsOverWordsParser();
const song = parser.parse(String(input.content || ""));
song.title = String(input.title || "");
song.artist = String(input.artist || "");
const formatter = new ChordSheetJS.ChordProFormatter();
process.stdout.write(formatter.format(song));
