const fs = require('fs-extra');
const path = require('path');

async function copyBuildToStatic() {
  try {
    console.log('Starting build copy process...');
    const buildDir = path.join(__dirname, 'build');
    const staticDir = path.join(__dirname, '..','static');

    if (!fs.existsSync(buildDir)) {
      console.error('Build directory not found. Please run "npm run build" first.');
      process.exit(1);
    }
    if (fs.existsSync(staticDir)) {
      console.log('Clearing existing static directory...');
      await fs.emptyDir(staticDir);
    } else {
      console.log('Creating static directory...');
      await fs.ensureDir(staticDir);
    }    
    await fs.copy(buildDir, staticDir);    
  
    const files = await fs.readdir(staticDir);
    console.log(`Files in static/: ${files.slice(0, 5).join(', ')}${files.length > 5 ? '...' : ''}`);

  } catch (error) {
    console.error('Error copying build files:', error.message);
    process.exit(1);
  }
}


copyBuildToStatic();
