const fs = require('fs-extra');
const path = require('path');

const srcDir = path.join(__dirname, 'build');
const destDir = path.join(__dirname, '..', 'static', 'build');

try {
  // Ensure destination directory exists
  fs.ensureDirSync(destDir);
  
  // Empty destination directory
  fs.emptyDirSync(destDir);
  
  // Copy build files
  fs.copySync(srcDir, destDir);
  
  console.log('✅ React build copied to Flask static folder');
} catch (error) {
  console.error('❌ Failed to copy React build:', error.message);
  process.exit(1);
}
