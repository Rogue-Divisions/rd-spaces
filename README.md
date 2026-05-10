# Spaces by Rogue Divisions — landing page

Live: https://spaces.roguedivisions.com
Host: Cloudflare Workers (static assets from `./public`)
Worker name: `rd-spaces`

## Publish flow

1. Edit files in `public/` (HTML, CSS, assets).
2. `git add . && git commit -m "<change>" && git push`
3. If GitHub auto-deploy is wired up, that's it. Otherwise:

   ```
   set -a && source ../intranet/.env && set +a
   npx wrangler@latest deploy
   ```

## Notes

- `noindex, nofollow` meta tag is set — page is unlisted, by-referral only.
- DNS is managed automatically via `custom_domain = true` in `wrangler.toml`.
- Reuses the Cloudflare API token from `../intranet/.env`.
