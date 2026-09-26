import fs from "node:fs";
import path from "node:path";

const root=process.cwd();
const packageDir=path.join(root,"android","app","src","main","java","com","jakeharvey","ash");
fs.mkdirSync(packageDir,{recursive:true});

for(const name of ["AshWakePlugin.java","AshWakeService.java","MainActivity.java"]){
  fs.copyFileSync(path.join(root,"native","android",name),path.join(packageDir,name));
}

const manifestPath=path.join(root,"android","app","src","main","AndroidManifest.xml");
let manifest=fs.readFileSync(manifestPath,"utf8");
const permissions=[
  "android.permission.RECORD_AUDIO",
  "android.permission.FOREGROUND_SERVICE",
  "android.permission.FOREGROUND_SERVICE_MICROPHONE",
  "android.permission.POST_NOTIFICATIONS",
  "android.permission.WAKE_LOCK"
];
for(const permission of permissions){
  if(!manifest.includes(permission)){
    manifest=manifest.replace("<application","<uses-permission android:name=\""+permission+"\" />\n\n    <application");
  }
}
if(!manifest.includes("AshWakeService")){
  manifest=manifest.replace("</application>",
    "        <service\n"+
    "            android:name=\".AshWakeService\"\n"+
    "            android:enabled=\"true\"\n"+
    "            android:exported=\"false\"\n"+
    "            android:foregroundServiceType=\"microphone\" />\n"+
    "    </application>");
}
fs.writeFileSync(manifestPath,manifest);
console.log("Ash Android native wake service patched.");
