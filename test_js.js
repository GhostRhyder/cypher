const fs = require('fs');
const content = fs.readFileSync('new_dashboard_patched.py', 'utf-8');
const match = content.match(/<script>(.*?)<\/script>/s);
if (match) {
    fs.writeFileSync('temp.js', match[1]);
    console.log("Extracted");
}
