import * as THREE from "three";

function makeMaterial(color, options={}) {
  return new THREE.MeshPhysicalMaterial({
    color,
    metalness: options.metalness ?? 0.88,
    roughness: options.roughness ?? 0.24,
    clearcoat: options.clearcoat ?? 0.82,
    clearcoatRoughness: options.clearcoatRoughness ?? 0.18,
    emissive: options.emissive ?? 0x000000,
    emissiveIntensity: options.emissiveIntensity ?? 0
  });
}

function addEye(group, x, glowColor) {
  const socket = new THREE.Mesh(
    new THREE.SphereGeometry(0.175, 28, 18),
    makeMaterial(0x070a0f,{metalness:.95,roughness:.18})
  );
  socket.scale.set(1.45,.62,.36);
  socket.position.set(x,.19,.665);
  group.add(socket);

  const iris = new THREE.Mesh(
    new THREE.SphereGeometry(.092,24,16),
    makeMaterial(glowColor,{metalness:.35,roughness:.16,emissive:glowColor,emissiveIntensity:3.2})
  );
  iris.scale.set(1.25,.58,.22);
  iris.position.set(x,.19,.722);
  group.add(iris);

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(.115,.012,8,40),
    new THREE.MeshBasicMaterial({color:glowColor,transparent:true,opacity:.92})
  );
  ring.scale.set(1.36,.7,1);
  ring.position.set(x,.19,.746);
  group.add(ring);
}

function addFacePlate(group, x, y, sx, sy, rz, material) {
  const plate = new THREE.Mesh(new THREE.BoxGeometry(.34,.46,.075),material);
  plate.position.set(x,y,.64);
  plate.scale.set(sx,sy,1);
  plate.rotation.z=rz;
  group.add(plate);
}

function createAshHead(mobile=false) {
  const root=new THREE.Group();
  const shell=makeMaterial(0x101821,{metalness:.94,roughness:.2,clearcoat:1,clearcoatRoughness:.12});
  const plate=makeMaterial(0x1d2730,{metalness:.9,roughness:.24});
  const dark=makeMaterial(0x070a0e,{metalness:.96,roughness:.16});
  const amber=0xff9c22, cyan=0x38d6ff;

  const skull=new THREE.Mesh(new THREE.SphereGeometry(1,mobile?36:56,mobile?24:40),shell);
  skull.scale.set(.78,1.02,.72);
  root.add(skull);

  const brow=new THREE.Mesh(new THREE.SphereGeometry(.82,mobile?32:48,mobile?18:28,0,Math.PI*2,0,Math.PI*.48),plate);
  brow.scale.set(.78,.46,.73);
  brow.position.set(0,.36,.065);
  root.add(brow);

  const jaw=new THREE.Mesh(new THREE.CylinderGeometry(.46,.61,.62,8,1,false),plate);
  jaw.position.set(0,-.62,.20);
  jaw.rotation.y=Math.PI/8;
  root.add(jaw);

  const chin=new THREE.Mesh(new THREE.CylinderGeometry(.29,.40,.23,8),dark);
  chin.position.set(0,-.94,.31);
  chin.rotation.y=Math.PI/8;
  root.add(chin);

  addFacePlate(root,-.48,-.17,.78,1.05,-.20,plate);
  addFacePlate(root,.48,-.17,.78,1.05,.20,plate);

  const forehead=new THREE.Mesh(new THREE.BoxGeometry(.08,.57,.055),makeMaterial(amber,{metalness:.45,roughness:.18,emissive:amber,emissiveIntensity:1.7}));
  forehead.position.set(0,.56,.696);
  root.add(forehead);

  addEye(root,-.27,cyan);
  addEye(root,.27,amber);

  const nose=new THREE.Mesh(new THREE.ConeGeometry(.105,.43,4),dark);
  nose.rotation.x=Math.PI/2;
  nose.rotation.z=Math.PI/4;
  nose.position.set(0,-.08,.755);
  root.add(nose);

  const mouth=new THREE.Mesh(
    new THREE.TorusGeometry(.205,.014,8,36,Math.PI*.96),
    new THREE.MeshBasicMaterial({color:amber,transparent:true,opacity:.72})
  );
  mouth.rotation.z=Math.PI*.02;
  mouth.position.set(-.008,-.54,.68);
  root.add(mouth);

  for(const side of [-1,1]){
    const temple=new THREE.Mesh(
      new THREE.TorusGeometry(.255,.03,10,48),
      new THREE.MeshStandardMaterial({
        color:side<0?cyan:amber,
        emissive:side<0?cyan:amber,
        emissiveIntensity:2.4,
        metalness:.5,
        roughness:.22
      })
    );
    temple.rotation.y=Math.PI/2;
    temple.position.set(side*.72,.02,.03);
    root.add(temple);

    const templeCore=new THREE.Mesh(new THREE.CylinderGeometry(.16,.16,.085,36),dark);
    templeCore.rotation.z=Math.PI/2;
    templeCore.position.set(side*.73,.02,.03);
    root.add(templeCore);
  }

  const neck=new THREE.Mesh(new THREE.CylinderGeometry(.37,.50,.66,12),shell);
  neck.position.set(0,-1.16,-.06);
  root.add(neck);

  const collar=new THREE.Mesh(new THREE.TorusGeometry(.52,.075,10,48),plate);
  collar.rotation.x=Math.PI/2;
  collar.position.set(0,-1.42,-.04);
  root.add(collar);

  // Holographic orbital rings around the head.
  [
    [1.22,.009,amber,1.35,.10],
    [1.36,.007,cyan,1.48,-.12],
    [1.06,.006,amber,1.62,.28]
  ].forEach(([r,t,c,rx,rz])=>{
    const ring=new THREE.Mesh(
      new THREE.TorusGeometry(r,t,6,mobile?72:110),
      new THREE.MeshBasicMaterial({color:c,transparent:true,opacity:.48})
    );
    ring.rotation.x=rx;ring.rotation.z=rz;
    root.add(ring);
  });

  const count=mobile?44:78;
  const positions=new Float32Array(count*3);
  for(let i=0;i<count;i++){
    const a=i*2.3999632297;
    const radius=1.08+(i%9)*.045;
    positions[i*3]=Math.cos(a)*radius;
    positions[i*3+1]=((i%13)-6)*.105;
    positions[i*3+2]=Math.sin(a)*radius*.38;
  }
  const particles=new THREE.BufferGeometry();
  particles.setAttribute("position",new THREE.BufferAttribute(positions,3));
  const points=new THREE.Points(
    particles,
    new THREE.PointsMaterial({color:amber,size:mobile?.018:.024,transparent:true,opacity:.66,sizeAttenuation:true})
  );
  root.add(points);

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

  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,mobile?1.25:1.7));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.18;
  renderer.setClearColor(0x000000,0);

  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(mobile?28:25,1,.1,30);
  camera.position.set(0,.01,mobile?4.45:4.05);

  const root=createAshHead(mobile);
  root.position.y=.14;
  root.rotation.y=-.06;
  scene.add(root);

  scene.add(new THREE.HemisphereLight(0x7bdfff,0x140b04,1.35));
  const warm=new THREE.PointLight(0xff861c,mobile?30:42,9,2);
  warm.position.set(2.4,1.5,3.0);scene.add(warm);
  const cool=new THREE.PointLight(0x37d8ff,mobile?22:34,9,2);
  cool.position.set(-2.2,.8,2.1);scene.add(cool);
  const rim=new THREE.DirectionalLight(0xffffff,1.25);
  rim.position.set(0,3,-2);scene.add(rim);

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
  const ro=new ResizeObserver(resize);ro.observe(host);resize();

  const io=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting!==false},{threshold:.01});
  io.observe(host);

  const clock=new THREE.Clock();
  const animate=()=>{
    if(disposed)return;
    raf=requestAnimationFrame(animate);
    if(!visible||document.hidden)return;
    const t=clock.getElapsedTime();
    const targetY=reduceMotion?-.06:(-.06+pointerX*.13+Math.sin(t*.36)*.025);
    const targetX=reduceMotion?0:(-pointerY*.055+Math.sin(t*.28)*.012);
    root.rotation.y+=(targetY-root.rotation.y)*.045;
    root.rotation.x+=(targetX-root.rotation.x)*.045;
    if(!reduceMotion)root.position.y=.14+Math.sin(t*.7)*.018;
    renderer.render(scene,camera);
  };

  canvas.dataset.threeReady="true";
  animate();

  return ()=>{
    if(disposed)return;
    disposed=true;
    cancelAnimationFrame(raf);
    ro.disconnect();io.disconnect();
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
