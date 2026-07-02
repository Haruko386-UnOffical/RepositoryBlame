# RepositoryBlame

Generate a contributor language contribution SVG using only GitHub Actions, `git blame`, and the GitHub commit API.
<div align="center">
   <picture>
  <img alt="Our repository blame graph" src="https://github.com/Haruko386-UnOffical/RepositoryBlame/blob/3f237c85f68dae7d734b7b5b8baa91d2ec0285aa/code-stats.svg" width="70%">
    </picture>
</div>

## How it works

1. The target repository only needs a workflow yml.
2. The Action repository contains this generator code.
3. The workflow checks out the full git history.
4. The generator runs `git blame --line-porcelain` on supported source files.
5. Each blamed line is resolved from its commit SHA through GitHub's commit API.
6. The result is rendered as an SVG and pushed to the `codeStats` branch.

## Usage in the target repository

Create `.github/workflows/generate-code-stats.yml`:

```yaml
name: Generate Code Stats

on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  generate:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate code stats SVG
        uses: Haruko386-UnOffical/RepositoryBlame@main
        with:
          output: dist/code-stats.svg
          title: "Code Stats"
          min-percent: "0.8"
          width: "900"
          github-token: ${{ secrets.GITHUB_TOKEN }}
          ignore: |
            vendor/**
            node_modules/**
            dist/**
            build/**
            target/**
            *.lock
          users: |
            Haruko386=Haruko386,tryeverypossible@163.com

      - name: Push SVG to codeStats branch
        uses: crazy-max/ghaction-github-pages@v4
        with:
          target_branch: codeStats
          build_dir: dist
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Replace `Haruko386-UnOffical/RepositoryBlame@main` with your real Action repository.

After generation, reference the SVG in your README:

```md
![Code Stats](https://github.com/Haruko386-UnOffical/RepositoryBlame/blob/3f237c85f68dae7d734b7b5b8baa91d2ec0285aa/code-stats.svg)
```


## Inputs

| Input | Default | Description |
|---|---:|---|
| `output` | `dist/code-stats.svg` | Output SVG path. |
| `title` | `Code Stats` | SVG title. |
| `width` | `900` | SVG width. |
| `min-percent` | `0.8` | Contributors below this percent are folded into the small-avatar area. |
| `ignore` | empty | Extra ignore glob patterns, one per line. |
| `users` | empty | Optional fallback aliases. Format: `GitHubUser=alias,email,name`. |
| `github-token` | empty | Token used to resolve commit SHA to GitHub account/avatar. |
