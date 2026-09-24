import * as THREE from "three";

function physical(color, options={}) {
  return new THREE.MeshPhysicalMaterial({
    color,
    metalness: options.metalness ?? .55,
    roughness: options.roughness ?? .2,
    clearcoat: options.clearcoat ?? .92,
    clearcoatRoughness: options.clearcoatRoughness ?? .12,
    emissive: options.emissive ?? 0x000000,
    emissiveIntensity: options.emissiveIntensity ?? 0
  });
}

function cylinderBetween(a,b,radius,material,segments=10){
  const start=new THREE.Vector3(...a),end=new THREE.Vector3(...b);
  const dir=end.clone().sub(start),len=dir.length();
  const mesh=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,len,segments),material);
  mesh.position.copy(start.clone().add(end).multiplyScalar(.5));
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),dir.normalize());
  return mesh;
}

function addEye(root,x,cyan,dark){
  const socket=new THREE.Mesh(new THREE.SphereGeometry(.108,24,16),dark);
  socket.scale.set(1.28,.48,.28);
  socket.position.set(x,.42,.603);
  root.add(socket);

  const lens=new THREE.Mesh(
    new THREE.SphereGeometry(.053,20,12),
    physical(cyan,{metalness:.18,roughness:.1,emissive:cyan,emissiveIntensity:2.6})
  );
  lens.scale.set(1.1,.62,.25);
  lens.position.set(x,.42,.642);
  root.add(lens);
}

function addChestCore(root,cyan,dark,chrome,mobile){
  const core=new THREE.Group();
  core.position.set(0,-1.76,.54);
  core.rotation.x=Math.PI/2;

  const outer=new THREE.Mesh(new THREE.CylinderGeometry(.31,.31,.085,mobile?36:54),chrome);
  core.add(outer);

  const recess=new THREE.Mesh(new THREE.CylinderGeometry(.245,.245,.095,mobile?36:54),dark);
  recess.position.y=.022;
  core.add(recess);

  const glow=new THREE.Mesh(
    new THREE.CylinderGeometry(.18,.18,.102,mobile?36:54),
    physical(cyan,{metalness:.16,roughness:.12,emissive:cyan,emissiveIntensity:4.8})
  );
  glow.position.y=.045;
  core.add(glow);

  const ring1=new THREE.Mesh(
    new THREE.TorusGeometry(.225,.018,8,mobile?40:64),
    new THREE.MeshBasicMaterial({color:cyan,transparent:true,opacity:.95})
  );
  ring1.rotation.x=Math.PI/2;
  ring1.position.z=.065;
  core.add(ring1);

  const ring2=new THREE.Mesh(
    new THREE.TorusGeometry(.135,.009,8,mobile?36:56),
    new THREE.MeshBasicMaterial({color:0xd8fbff,transparent:true,opacity:.9})
  );
  ring2.rotation.x=Math.PI/2;
  ring2.position.z=.071;
  core.add(ring2);

  root.add(core);

  const coreLight=new THREE.PointLight(cyan,mobile?9:16,3.2,2);
  coreLight.position.set(0,-1.72,1.15);
  root.add(coreLight);
}

function createReferenceRobot(mobile=false){
  const root=new THREE.Group();
  const white=physical(0xeef3f4,{metalness:.38,roughness:.16,clearcoat:1,clearcoatRoughness:.08});
  const whiteSoft=physical(0xd8e0e3,{metalness:.42,roughness:.2});
  const chrome=physical(0x9eabb1,{metalness:.94,roughness:.16,clearcoat:.65});
  const dark=physical(0x081016,{metalness:.9,roughness:.21,clearcoat:.35});
  const darkSoft=physical(0x111a21,{metalness:.78,roughness:.28});
  const cyan=0x25d9e9;

  // Upper torso / chest shell.
  const chest=new THREE.Mesh(new THREE.SphereGeometry(1,mobile?32:48,mobile?20:32),white);
  chest.scale.set(1.18,.77,.56);
  chest.position.set(0,-1.86,-.02);
  root.add(chest);

  const sternum=new THREE.Mesh(new THREE.BoxGeometry(.62,.78,.13),whiteSoft);
  sternum.position.set(0,-1.62,.48);
  sternum.rotation.x=-.06;
  root.add(sternum);

  const collar=new THREE.Mesh(new THREE.TorusGeometry(.47,.105,10,mobile?36:54),dark);
  collar.rotation.x=Math.PI/2;
  collar.position.set(0,-1.08,.02);
  root.add(collar);

  // Shoulder armor and upper arms.
  for(const side of [-1,1]){
    const shoulderJoint=new THREE.Mesh(new THREE.SphereGeometry(.23,mobile?24:36,16),dark);
    shoulderJoint.position.set(side*1.02,-1.53,.03);
    root.add(shoulderJoint);

    const shoulder=new THREE.Mesh(new THREE.SphereGeometry(.43,mobile?28:42,20),white);
    shoulder.scale.set(1.08,.66,.82);
    shoulder.position.set(side*1.1,-1.46,.05);
    shoulder.rotation.z=side*.1;
    root.add(shoulder);

    const capSeam=new THREE.Mesh(new THREE.TorusGeometry(.31,.015,8,mobile?32:48),chrome);
    capSeam.rotation.y=Math.PI/2;
    capSeam.position.set(side*1.22,-1.46,.05);
    root.add(capSeam);

    const upperArm=new THREE.Mesh(new THREE.CylinderGeometry(.24,.20,.9,mobile?20:30),whiteSoft);
    upperArm.position.set(side*1.14,-2.02,.01);
    upperArm.rotation.z=side*.11;
    root.add(upperArm);

    const elbow=new THREE.Mesh(new THREE.SphereGeometry(.19,mobile?20:28,14),dark);
    elbow.position.set(side*1.18,-2.47,.02);
    root.add(elbow);

    const armRing=new THREE.Mesh(new THREE.TorusGeometry(.205,.035,8,mobile?28:40),chrome);
    armRing.rotation.x=Math.PI/2;
    armRing.position.set(side*1.16,-2.31,.02);
    root.add(armRing);
  }

  // Mechanical neck inspired by the user's white humanoid reference.
  const neckCore=new THREE.Mesh(new THREE.CylinderGeometry(.265,.33,.76,12),dark);
  neckCore.position.set(0,-.82,-.01);
  root.add(neckCore);

  const neckRingTop=new THREE.Mesh(new THREE.TorusGeometry(.28,.03,8,mobile?32:48),chrome);
  neckRingTop.rotation.x=Math.PI/2;
  neckRingTop.position.set(0,-.5,.01);
  root.add(neckRingTop);

  for(const x of [-.22,-.12,.12,.22]){
    const upper=[x*.72,-.43,.02+Math.abs(x)*.4];
    const lower=[x,-1.11,.06];
    root.add(cylinderBetween(upper,lower,.022,x<0?chrome:darkSoft,mobile?8:12));
  }
  root.add(cylinderBetween([-.29,-.48,.04],[-.40,-1.05,.03],.026,darkSoft,mobile?8:12));
  root.add(cylinderBetween([.29,-.48,.04],[.40,-1.05,.03],.026,darkSoft,mobile?8:12));

  // Smooth human-like head.
  const head=new THREE.Mesh(new THREE.SphereGeometry(1,mobile?36:56,mobile?24:40),white);
  head.scale.set(.57,.72,.55);
  head.position.set(0,.05,.02);
  root.add(head);

  // Slight face plate and cheek shaping.
  const face=new THREE.Mesh(new THREE.SphereGeometry(.86,mobile?32:48,mobile?20:32),whiteSoft);
  face.scale.set(.55,.62,.48);
  face.position.set(0,.02,.19);
  root.add(face);

  const jaw=new THREE.Mesh(new THREE.CylinderGeometry(.31,.39,.42,10),whiteSoft);
  jaw.position.set(0,-.43,.22);
  root.add(jaw);

  const chin=new THREE.Mesh(new THREE.SphereGeometry(.22,mobile?20:28,14),white);
  chin.scale.set(1,.62,.72);
  chin.position.set(0,-.64,.34);
  root.add(chin);

  // Human-like robot facial details.
  addEye(root,-.19,cyan,dark);
  addEye(root,.19,cyan,dark);

  const nose=new THREE.Mesh(new THREE.ConeGeometry(.072,.31,5),whiteSoft);
  nose.rotation.x=Math.PI/2;
  nose.rotation.z=Math.PI/5;
  nose.position.set(0,.13,.635);
  root.add(nose);

  const mouth=new THREE.Mesh(new THREE.BoxGeometry(.22,.012,.018),darkSoft);
  mouth.position.set(0,-.24,.626);
  root.add(mouth);

  const browLine=new THREE.Mesh(new THREE.BoxGeometry(.5,.018,.02),chrome);
  browLine.position.set(0,.56,.548);
  browLine.rotation.z=.01;
  root.add(browLine);

  // Ear / temple mechanics.
  for(const side of [-1,1]){
    const ear=new THREE.Mesh(new THREE.CylinderGeometry(.14,.14,.09,mobile?24:36),dark);
    ear.rotation.z=Math.PI/2;
    ear.position.set(side*.57,.10,.02);
    root.add(ear);

    const earRing=new THREE.Mesh(
      new THREE.TorusGeometry(.11,.015,8,mobile?28:42),
      new THREE.MeshBasicMaterial({color:cyan,transparent:true,opacity:.78})
    );
    earRing.rotation.y=Math.PI/2;
    earRing.position.set(side*.62,.10,.02);
    root.add(earRing);
  }

  addChestCore(root,cyan,dark,chrome,mobile);

  // Thin holographic Ash halo, deliberately subtle so the robot remains the focal point.
  const halo=new THREE.Mesh(
    new THREE.TorusGeometry(1.54,.008,6,mobile?68:96),
    new THREE.MeshBasicMaterial({color:cyan,transparent:true,opacity:.24})
  );
  halo.rotation.x=1.36;
  halo.rotation.z=-.17;
  halo.position.y=-.28;
  root.add(halo);

  const pointCount=mobile?28:52;
  const p=new Float32Array(pointCount*3);
  for(let i=0;i<pointCount;i++){
    const a=i*2.3999632297,r=1.34+(i%7)*.05;
    p[i*3]=Math.cos(a)*r;
    p[i*3+1]=-.25+((i%11)-5)*.17;
    p[i*3+2]=Math.sin(a)*r*.32;
  }
  const pg=new THREE.BufferGeometry();
  pg.setAttribute("position",new THREE.BufferAttribute(p,3));
  root.add(new THREE.Points(pg,new THREE.PointsMaterial({
    color:cyan,size:mobile?.012:.017,transparent:true,opacity:.38,sizeAttenuation:true
  })));

  root.userData.variant="white-humanoid-cyan-core";
  return root;
}

export async function mountAshHero3D(canvas){
  if(!canvas)return()=>{};
  const mobile=matchMedia("(max-width:650px)").matches;
  const reduceMotion=matchMedia("(prefers-reduced-motion: reduce)").matches;
  let disposed=false,raf=0,visible=true;

  let renderer;
  try{
    renderer=new THREE.WebGLRenderer({
      canvas,
      alpha:true,
      antialias:!mobile,
      powerPreference:mobile?"low-power":"high-performance"
    });
  }catch(e){
    canvas.dataset.threeReady="error";
    throw e;
  }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,mobile?1.2:1.65));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.08;
  renderer.setClearColor(0x000000,0);

  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(mobile?28:26,1,.1,40);
  camera.position.set(0,.03,mobile?8.2:7.65);

  const root=createReferenceRobot(mobile);
  root.position.set(.04,.72,0);
  root.rotation.set(-.015,-.11,0);
  root.scale.setScalar(mobile?.94:1.04);
  scene.add(root);

  scene.add(new THREE.HemisphereLight(0xe8fbff,0x071015,mobile?1.55:1.85));

  const key=new THREE.DirectionalLight(0xffffff,mobile?3.2:4.1);
  key.position.set(2.2,3.7,4.6);
  scene.add(key);

  const cool=new THREE.PointLight(0x23ddea,mobile?16:24,8,2);
  cool.position.set(-2.4,.7,3.5);
  scene.add(cool);

  const rim=new THREE.PointLight(0xbfefff,mobile?10:16,8,2);
  rim.position.set(2.8,1.5,-1.5);
  scene.add(rim);

  const fill=new THREE.PointLight(0x7d8d98,mobile?5:8,6,2);
  fill.position.set(-1.8,-1.8,2.4);
  scene.add(fill);

  let pointerX=0,pointerY=0;
  const host=canvas.parentElement||canvas;
  const onPointer=e=>{
    const r=host.getBoundingClientRect();
    pointerX=((e.clientX-r.left)/Math.max(r.width,1)-.5)*2;
    pointerY=((e.clientY-r.top)/Math.max(r.height,1)-.5)*2;
  };
  const onLeave=()=>{pointerX=0;pointerY=0};
  host.addEventListener("pointermove",onPointer,{passive:true});
  host.addEventListener("pointerleave",onLeave,{passive:true});

  const resize=()=>{
    const r=host.getBoundingClientRect();
    const w=Math.max(1,Math.round(r.width)),h=Math.max(1,Math.round(r.height));
    renderer.setSize(w,h,false);
    camera.aspect=w/h;
    camera.updateProjectionMatrix();
  };
  const ro=new ResizeObserver(resize);
  ro.observe(host);
  resize();

  const io=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting!==false},{threshold:.01});
  io.observe(host);

  const clock=new THREE.Clock();
  const animate=()=>{
    if(disposed)return;
    raf=requestAnimationFrame(animate);
    if(!visible||document.hidden)return;

    const t=clock.getElapsedTime();
    const targetY=reduceMotion?-.11:(-.11+pointerX*.10+Math.sin(t*.32)*.018);
    const targetX=reduceMotion?-.015:(-.015-pointerY*.038+Math.sin(t*.25)*.008);
    root.rotation.y+=(targetY-root.rotation.y)*.04;
    root.rotation.x+=(targetX-root.rotation.x)*.04;
    if(!reduceMotion)root.position.y=.72+Math.sin(t*.62)*.014;

    renderer.render(scene,camera);
  };

  canvas.dataset.threeReady="true";
  canvas.dataset.model="white-humanoid-cyan-core";
  animate();

  return ()=>{
    if(disposed)return;
    disposed=true;
    cancelAnimationFrame(raf);
    ro.disconnect();
    io.disconnect();
    host.removeEventListener("pointermove",onPointer);
    host.removeEventListener("pointerleave",onLeave);
    scene.traverse(obj=>{
      obj.geometry?.dispose?.();
      if(Array.isArray(obj.material))obj.material.forEach(m=>m.dispose?.());
      else obj.material?.dispose?.();
    });
    renderer.dispose();
  };
}
