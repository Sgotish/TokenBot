const fs=require('node:fs');
const r=require('../integrations/windows-codex/native-menu/ota-client.cjs').verify(fs.readFileSync(process.argv[2]));
fs.writeFileSync(process.argv[3],JSON.stringify(r.assets[0]));
