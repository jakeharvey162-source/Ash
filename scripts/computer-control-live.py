from __future__ import annotations
import base64, io, json, os, pathlib, re, sys, time
import httpx
from PIL import Image, ImageDraw, ImageFont

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"desktop_worker"))
from ash_agent import AshPythonAgent
from computer_control import AshComputerController, ScreenFrame

APP=os.environ.get("ASH_LIVE_URL","https://meet-ash.jakeharvey162.workers.dev/").rstrip("/")
cfg=httpx.get(APP+"/config.js",timeout=15).text
def pick(name:str)->str:
    m=re.search(rf'{name}\s*:\s*["\']([^"\']+)["\']',cfg)
    return m.group(1) if m else ""
base=pick("SUPABASE_URL").rstrip("/")
key=pick("SUPABASE_PUBLISHABLE_KEY")
gateway=pick("ASH_GATEWAY_URL")
if not (base and key and gateway): raise SystemExit("Ash live config missing.")

stamp=int(time.time()*1000)
signup=httpx.post(base+"/auth/v1/signup",headers={"apikey":key,"Content-Type":"application/json"},json={
    "email":f"ash-computer-{stamp}@example.com",
    "password":f"ComputerControl-{stamp}-A9!",
    "data":{"full_name":"Ash Computer Acceptance"},
},timeout=20)
signup.raise_for_status()
session=signup.json(); token=session.get("access_token")
headers={"apikey":key,"Authorization":"Bearer "+token,"Content-Type":"application/json"}
pair=httpx.post(base+"/functions/v1/ash-device-link",headers=headers,json={"action":"create_pairing"},timeout=20);pair.raise_for_status()
claim=httpx.post(base+"/functions/v1/ash-device-link",headers={"Content-Type":"application/json"},json={
    "action":"claim_pairing","code":pair.json().get("code"),"device_name":"Computer Control CI","platform":"linux-ci",
    "app_version":"computer-control-live","capabilities":{"computer_control":True,"screen_vision":True},
},timeout=20);claim.raise_for_status()
device=claim.json()
os.environ["ASH_GATEWAY_URL"]=gateway
os.environ["ASH_SUPABASE_PUBLISHABLE_KEY"]=key
agent=AshPythonAgent(); agent.set_device_credentials(device["device_id"],device["device_secret"])

def frame(done=False):
    img=Image.new("RGB",(800,600),(244,246,249))
    d=ImageDraw.Draw(img)
    d.rectangle((0,0,800,72),fill=(18,25,36))
    d.text((24,24),"ASH COMPUTER CONTROL ACCEPTANCE",fill=(255,255,255))
    if done:
        d.rounded_rectangle((255,215,545,355),radius=18,fill=(225,255,237),outline=(40,160,95),width=3)
        d.text((315,272),"TASK COMPLETE",fill=(22,104,58))
    else:
        d.text((250,170),"Please complete the safe UI task below.",fill=(45,55,68))
        d.rounded_rectangle((300,250,500,330),radius=16,fill=(30,125,255))
        d.text((344,282),"CLICK ME",fill=(255,255,255))
    out=io.BytesIO(); img.save(out,"JPEG",quality=92)
    return ScreenFrame(base64.b64encode(out.getvalue()).decode("ascii"),800,600)

class FakeSize:
    width=800;height=600
class FakePyAutoGui:
    FAILSAFE=True;PAUSE=0
    def __init__(self): self.calls=[]
    def size(self): return FakeSize()
    def moveTo(self,x,y,duration=0): self.calls.append(("move",x,y))
    def click(self,x,y): self.calls.append(("click",x,y))
    def doubleClick(self,x,y,interval=0): self.calls.append(("double_click",x,y))
    def write(self,text,interval=0): self.calls.append(("type_text",text))
    def press(self,key): self.calls.append(("press",key))
    def hotkey(self,*keys): self.calls.append(("hotkey",keys))
    def scroll(self,amount): self.calls.append(("scroll",amount))

class HarnessController(AshComputerController):
    def __init__(self,agent):
        self.agent=agent
        self.enabled=True
        self.pyautogui=FakePyAutoGui()
        self.frames=[frame(False),frame(True)]
        self.index=0
    def capture(self):
        value=self.frames[min(self.index,len(self.frames)-1)]
        self.index+=1
        return value
    def execute_action(self,action):
        return super().execute_action(action)

controller=HarnessController(agent)
result=controller.run_goal("Click the blue CLICK ME button once. When the screenshot says TASK COMPLETE, stop and report success.",max_steps=3)
clicks=[c for c in controller.pyautogui.calls if c[0] in {"click","double_click"}]
if not result.get("ok"):
    raise SystemExit("Computer control did not visually verify completion: "+json.dumps(result))
if not clicks:
    raise SystemExit("Computer control never produced a click.")
_,x,y=clicks[0]
if not (285<=x<=515 and 235<=y<=345):
    raise SystemExit(f"Computer vision click was outside target region: {(x,y)}")
print("ASH COMPUTER CONTROL LIVE LOOP: PASS")
print(json.dumps({"ok":True,"click":clicks[0],"trace":result.get("trace",[])},indent=2))
