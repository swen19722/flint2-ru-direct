# Flint 2 — RU Direct Extended

A plain-text, automatically updated Russian-domain bypass list for **GL.iNet Flint 2 / AmneziaWG**, using VPN Dashboard → **Exclude Specified Domain / IP List** → **Subscription URL**.

## Subscription URL

```text
https://raw.githubusercontent.com/swen19722/flint2-ru-direct/main/ru-direct-extended.domains.txt
```

## Sources

- [ru-direct standard](https://raw.githubusercontent.com/kyoresuas/ru-direct/release/ru-standard.domains.txt) — base list.
- [Tachyon ru_only_inside](https://raw.githubusercontent.com/Dushnilin/tachyon-lists/main/release/domains/ru_only_inside.lst) — services that may require a Russian IP.
- [extra-domains.txt](extra-domains.txt) — additional exceptions (currently `mosoblgaz.ru` and `mosenergosbyt.ru`).

[GitHub Actions](.github/workflows/update-domains.yml) rebuilds the file daily at 03:17 UTC and whenever personal exceptions change. It validates both upstream sources, merges, deduplicates and sorts domains. A failed download **does not overwrite** the last successful output.

To add another site: edit `extra-domains.txt`, add its root domain on a new line and commit. The existing Flint 2 URL remains unchanged.

## Important

- **Use Exclude**, not Specified: every listed destination goes **outside the VPN** through the normal WAN.
- The generated file has **only domains**, one per line, without comments or URLs.
- No credentials, private VPN data or router configuration should be committed here.
- Review source changes occasionally: a broader bypass list reduces VPN coverage.
- A GitHub Actions scheduled run can be delayed, and inactive public repositories may have scheduled workflows disabled after prolonged inactivity.
- If the job fails to push, check Settings → Actions → General → Workflow permissions and repository branch protection.
- Switch the router to this URL only after checking the file in GitHub and testing the site access.
