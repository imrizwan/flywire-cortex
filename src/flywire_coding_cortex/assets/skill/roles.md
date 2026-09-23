# Role → coding drive map

FlyWire-style role names are **coding lenses** driven by real population rates.

| Role | Drive | Agent action |
|---|---|---|
| `lc4` / `lplc2` | risk / loom | Scan blast radius, security, regressions |
| `gf` | escape / stop | Do not ship; unblocker; halt feature work |
| `dnp09` | forward | Implement the requested change |
| `mdn` | reverse | Revert / undo bad direction |
| `dna01` / `dna02` | steer | Write L vs R design tradeoff, then choose |
| `dng11` | groom | Cleanup, rename, lint-only |
| `escw` | effort under pressure | Polish without scope creep |
| `ascending` | proprioception | Read local conventions before inventing |
| `sensory` | external constraint | Honor ticket / failing test / user constraint |

Primary drive comes from `flywire-cortex signals` (`primary` field). Support roles may advise but must not override.
