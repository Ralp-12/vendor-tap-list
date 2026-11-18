# Welcome to your Lovable project

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Open your project in the [Lovable editor](https://lovable.dev) and keep building.

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Full ownership**: this code is yours.

> **Do NOT connect this project to GitHub sync.**
>
> This repo holds TWO versions of Vendor Tap List in one place: the Python
> booth version at the repo root (`server.py`, `index.html`, `admin.html`)
> and this web version under `web/`. Lovable's GitHub sync always pushes
> to the repo **root**. If you turn it on, Lovable will write its files
> over the root — it can overwrite or clash with the Python booth version
> (same filenames like `README.md`, plus its own `package.json` and config
> files at the root), and changes made in Lovable would land in the wrong
> place. The booth version could stop working, and untangling the two
> would mean sorting out which root files belong to which version.
> Keep the two versions separate by hand: web changes go under `web/`,
> booth changes stay at the root. See `WEB-VERSION.md` in this folder.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>/web
npm i
npm run dev
```

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS
