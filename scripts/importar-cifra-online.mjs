#!/usr/bin/env node
import { searchCifraClub, fetchCifraClubSong } from "../src/cifraclub.mjs";

const args = process.argv.slice(2);
const title = String(args[0] || "").trim();
const artist = String(args[1] || "").trim();
const fetchFirst = args.includes("--first");

if (!title) {
  console.error('Uso: npm run import:cifra -- "TÍTULO" "ARTISTA opcional" [--first]');
  process.exit(1);
}

try {
  const query = [title, artist].filter(Boolean).join(" ");
  const results = await searchCifraClub(query, 8);

  if (!results.length) {
    console.error("No se encontraron resultados.");
    process.exit(2);
  }

  if (!fetchFirst) {
    process.stdout.write(JSON.stringify({ query, results }, null, 2) + "\n");
  } else {
    const song = await fetchCifraClubSong(results[0].url);
    process.stdout.write(JSON.stringify({ match: results[0], song }, null, 2) + "\n");
  }
} catch (error) {
  console.error(error?.message || String(error));
  process.exit(3);
}
