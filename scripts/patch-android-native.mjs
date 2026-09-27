import fs from "node:fs";
import path from "node:path";

const root=process.cwd();
const packageDir=path.join(root,"android","app","src","main","java","com","jakeharvey","ash");
fs.mkdirSync(packageDir,{recursive:true});

for(const name of ["AshWakePlugin.java","AshWakeService.java","AshBootReceiver.java","MainActivity.java"]){
  fs.copyFileSync(path.join(root,"native","android",name),path.join(packageDir,name));
}

const manifestPath=path.join(root,"android","app","src","main","AndroidManifest.xml");
let manifest=fs.readFileSync(manifestPath,"utf8");
const permissions=[
  "android.permission.RECORD_AUDIO",
  "android.permission.FOREGROUND_SERVICE",
  "android.permission.FOREGROUND_SERVICE_MICROPHONE",
  "android.permission.POST_NOTIFICATIONS",
  "android.permission.WAKE_LOCK",
  "android.permission.RECEIVE_BOOT_COMPLETED"
];
for(const permission of permissions){
  if(!manifest.includes(permission)){
    manifest=manifest.replace("<application","<uses-permission android:name=\""+permission+"\" />\n\n    <application");
  }
}
if(!manifest.includes("AshBootReceiver")){
  manifest=manifest.replace("</application>",
    "        <receiver\n"+
    "            android:name=\".AshBootReceiver\"\n"+
    "            android:enabled=\"true\"\n"+
    "            android:exported=\"false\">\n"+
    "            <intent-filter>\n"+
    "                <action android:name=\"android.intent.action.BOOT_COMPLETED\" />\n"+
    "                <action android:name=\"android.intent.action.MY_PACKAGE_REPLACED\" />\n"+
    "                <action android:name=\"android.intent.action.QUICKBOOT_POWERON\" />\n"+
    "            </intent-filter>\n"+
    "        </receiver>\n"+
    "    </application>");
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


/* Google Play release hardening. The Android project is generated in CI, so
   keep store requirements reproducible here instead of editing generated files. */
const variablesPath=path.join(root,"android","variables.gradle");
if(fs.existsSync(variablesPath)){
  let variables=fs.readFileSync(variablesPath,"utf8");
  variables=variables.replace(/compileSdkVersion\s*=\s*\d+/,"compileSdkVersion = 36");
  variables=variables.replace(/targetSdkVersion\s*=\s*\d+/,"targetSdkVersion = 36");
  fs.writeFileSync(variablesPath,variables);
}

const appGradlePath=path.join(root,"android","app","build.gradle");
if(fs.existsSync(appGradlePath)){
  let gradle=fs.readFileSync(appGradlePath,"utf8");
  const versionCode=Math.max(1,Number.parseInt(process.env.ASH_VERSION_CODE || process.env.GITHUB_RUN_NUMBER || "1",10) || 1);
  const versionName=(process.env.ASH_VERSION_NAME || process.env.npm_package_version || "1.1.1").replace(/[^0-9A-Za-z._-]/g,"");
  gradle=gradle.replace(/versionCode\s+\d+/,"versionCode "+versionCode);
  gradle=gradle.replace(/versionName\s+["'][^"']+["']/,'versionName "'+versionName+'"');

  if(process.env.ASH_RELEASE_STORE_FILE && !gradle.includes("ASH_RELEASE_STORE_FILE")){
    gradle=gradle.replace("android {", `android {
    signingConfigs {
        release {
            storeFile file(System.getenv("ASH_RELEASE_STORE_FILE"))
            storePassword System.getenv("ASH_RELEASE_STORE_PASSWORD")
            keyAlias System.getenv("ASH_RELEASE_KEY_ALIAS")
            keyPassword System.getenv("ASH_RELEASE_KEY_PASSWORD")
        }
    }`);
    gradle=gradle.replace(/release\s*\{/, `release {
            signingConfig signingConfigs.release`);
  }
  fs.writeFileSync(appGradlePath,gradle);
}
console.log("Ash Android Play configuration enforced: target/compile SDK 36, deterministic versioning, optional release signing.");
