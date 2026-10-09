// Shared semantic-release config for a Factorio mod, used by release/action.yml through --extends.
// Conventional commits pick the version and fill changelog.txt in the format the game parses; semantic-release-factorio
// sets info.json, zips the mod and uploads it to the mod portal; the zip is also attached to the GitHub release.
// The repository comes from the git remote, the branch from `branches`: the first one that exists on the remote.

const types = [
  ["info", "Info", "patch"],
  ["feat", "Features", "minor"],
  ["feature", "Features", "minor"],
  ["gui", "Gui", "patch"],
  ["balance", "Balancing", "patch"],
  ["perf", "Optimizations", "patch"],
  ["performance", "Optimizations", "patch"],
  ["compat", "Compatibility", "patch"],
  ["compatibility", "Compatibility", "patch"],
  ["fix", "Bugfixes", "patch"],
  ["graphics", "Graphics", "patch"],
  ["sound", "Sounds", "patch"],
  ["locale", "Locale", "patch"],
  ["translate", "Translation", "patch"],
  ["control", "Control", "patch"],
  ["other", "Changes", "patch"],
];

module.exports = {
  branches: ["main", "master"],
  plugins: [
    [
      "@semantic-release/commit-analyzer",
      {
        preset: "conventionalcommits",
        releaseRules: [
          { breaking: true, release: "major" },
          ...types.map(([type, , release]) => ({ type, release })),
        ],
      },
    ],
    [
      "@semantic-release/release-notes-generator",
      {
        preset: "conventionalcommits",
        writerOpts: {
          headerPartial:
            "---------------------------------------------------------------------------------------------------\n" +
            "Version: {{version}}\nDate: {{#if date}}{{date}}{{else}}????{{/if}}\n",
          footerPartial: "",
          commitPartial: "{{#if scope}}[{{scope}}] {{/if}}{{~subject}}",
          mainTemplate:
            "{{> header}}\n{{#each commitGroups}}\n  {{title}}:\n{{#each commits}}\n    - {{> commit root=@root}}\n{{/each}}\n{{/each}}",
        },
        presetConfig: {
          types: types.map(([type, section]) => ({ type, section })),
        },
      },
    ],
    "semantic-release-factorio",
    [
      "@semantic-release/github",
      {
        assets: [{ path: "*_*.*.*.zip", label: "Packaged Mod" }],
      },
    ],
    [
      "@semantic-release/git",
      {
        assets: ["changelog.txt", "info.json"],
      },
    ],
  ],
};
