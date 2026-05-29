import fs from 'node:fs';
import { parse } from 'csv-parse';

export async function readUrls(csvPath) {
  const rows = [];
  const parser = fs.createReadStream(csvPath).pipe(parse({
    columns: false,
    skip_empty_lines: true,
    trim: true,
    relax_column_count: true,
  }));
  for await (const row of parser) {
    if (row.length < 2) continue;
    const [rank, url] = row;
    if (!rank || !url) continue;
    rows.push({ rank: String(rank), url: String(url) });
  }
  return rows;
}
