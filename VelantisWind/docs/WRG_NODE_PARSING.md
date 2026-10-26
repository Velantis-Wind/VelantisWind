# WRG node records

The metadata reader, full climate loader and automatic spacing orientation use
one structural rule for whitespace-delimited records with an optional
single-token identifier:

`[ID] x y z h A_total k_total power_density N [frequency A_sector k_sector] * N`

There must be exactly `8 + 3*N` fields without an ID, or `9 + 3*N` with an ID;
`N` must be a positive integer. These counts cannot both fit the same record.
The full loader validates every node; the lightweight metadata reader examines
only the first node of each WRG or ZIP member.

## Units

The structural check never guesses columns from physical magnitudes or rescales
values. Existing conversions are preserved:

| Field | WRG value | Loaded value |
| --- | --- | --- |
| Coordinates, elevation and height | metres | metres |
| Sector frequency | per mille (percent times 10) | probability, normalized by the sum of the raw frequencies to compensate rounding |
| Sector Weibull A | m/s times 10 | raw A / 10, in m/s |
| Sector Weibull k | k times 100 | raw k / 100 |

The total A/k and power-density header fields are not substituted for the
sectoral climate. Orientation uses the sectoral third Weibull moment with the
same A/k scales; the common frequency factor cancels in its relative energies.

## Identifier policy and limits

An ID convertible by Python `float()` to a **finite** number is deliberately
unsupported (`001`, `1e3`, `+5`, `1.`, `1_000`, `1e-999`). Otherwise a finite
numeric field inserted into an ID-free record can make its X look like an ID,
shifting the climate silently. The selected ID reading is rejected with its
source, physical line and reason; no alternative reading is attempted.

Text IDs (`GridPoint`, `0x10`) and IDs converting to nonfinite values (`nan`,
`inf`, `Infinity`, `1e999`) remain supported. This intentionally rejects some
files accepted by the older heuristic. Numeric node and climate values must
remain finite in the full loader, and numeric node headers in the light reader.

This policy rejects adding exactly one finite numeric token to an otherwise
unchanged valid ID-free row, wherever it is inserted. It cannot detect every
alteration that forms another accepted structure, including compensating
insertions/deletions. Grid or uniform-height heuristics are not imposed.
Fixed-width identifiers containing spaces remain outside the supported format.

The orientation reader keeps its 1–72 sector limit. An invalid first node fails
sector detection; its public angle wrapper returns `None`. Rejected later
sampled nodes are omitted, which can change the dominant angle.
