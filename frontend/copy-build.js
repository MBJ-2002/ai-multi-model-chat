const fs = require('fs-extra');
const path = require('path');

const srcDir = path.join(__dirname, 'build');
const destDir = path.join(__dirname, '..', 'static', 'build');

fs.emptyDirSync(destDir);
fs.copySync(srcDir, destDir);

console.log('React build copied to Flask static folder');
