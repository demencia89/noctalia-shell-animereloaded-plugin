#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const REGISTRY_VERSION = 1;
const ROOT_DIR = path.join(__dirname, '..', '..');
const REGISTRY_PATH = path.join(ROOT_DIR, 'registry.json');

function getLastCommitDate(filePath) {
  try {
    const result = execSync(`git log -1 --follow --format=%cI -- "${filePath}"`, {
      cwd: ROOT_DIR,
      encoding: 'utf8'
    }).trim();
    if (result) return result;
  } catch (_) {
    // fall through to the filesystem timestamp
  }
  try {
    return fs.statSync(filePath).mtime.toISOString();
  } catch (_) {
    try {
      return new Date().toISOString();
    } catch (_) {
      return null;
    }
  }
}

function isPluginDirectory(dirPath) {
  return fs.existsSync(path.join(dirPath, 'manifest.json'));
}

function readPluginManifest(dirPath) {
  const manifestPath = path.join(dirPath, 'manifest.json');
  try {
    return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  } catch (error) {
    console.error(`Error reading manifest from ${dirPath}: ${error.message}`);
    return null;
  }
}

function extractRegistryEntry(manifest, dirPath) {
  const manifestPath = path.join(dirPath, 'manifest.json');
  return {
    id: manifest.id,
    name: manifest.name,
    version: manifest.version,
    official: manifest.official || false,
    author: manifest.author,
    description: manifest.description,
    repository: manifest.repository,
    minNoctaliaVersion: manifest.minNoctaliaVersion,
    license: manifest.license,
    tags: manifest.tags || [],
    lastUpdated: getLastCommitDate(manifestPath)
  };
}

function scanPlugins() {
  const plugins = [];
  const items = fs.readdirSync(ROOT_DIR, { withFileTypes: true });

  for (const item of items) {
    if (!item.isDirectory() || item.name.startsWith('.') || item.name === 'node_modules' || item.name === 'scripts') {
      continue;
    }

    const dirPath = path.join(ROOT_DIR, item.name);
    if (!isPluginDirectory(dirPath)) continue;

    const manifest = readPluginManifest(dirPath);
    if (!manifest) continue;

    plugins.push(extractRegistryEntry(manifest, dirPath));
    console.log(`- Found plugin: ${manifest.name} (${manifest.id})`);
  }

  return plugins;
}

function writeRegistry(plugins) {
  plugins.sort((a, b) => a.id.localeCompare(b.id));
  const content = JSON.stringify({ version: REGISTRY_VERSION, plugins }, null, 2) + '\n';
  fs.writeFileSync(REGISTRY_PATH, content, 'utf8');
}

function main() {
  console.log('Scanning for plugins...');
  writeRegistry(scanPlugins());
  console.log(`Registry updated successfully at ${REGISTRY_PATH}`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error('Error updating registry:', error);
    process.exit(1);
  }
}
