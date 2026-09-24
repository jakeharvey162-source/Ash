const CACHE="ash-mobile-v4";
const CORE=["/","/index.html","/manifest.webmanifest","/icons/icon-192.svg","/icons/icon-512.svg"];
const STATIC_RE=/\.(?:js|css|webp|png|jpg|jpeg|svg|woff2?)$/i;

self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting()));
});

self.addEventListener("activate",event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET")return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;

  if(STATIC_RE.test(url.pathname)){
    event.respondWith((async()=>{
      const cached=await caches.match(request);
      const refresh=fetch(request).then(response=>{
        if(response.ok)caches.open(CACHE).then(cache=>cache.put(request,response.clone())).catch(()=>{});
        return response;
      }).catch(()=>cached||Response.error());
      return cached||refresh;
    })());
    return;
  }

  if(request.mode==="navigate"){
    event.respondWith((async()=>{
      try{
        const response=await fetch(request);
        if(response.ok)caches.open(CACHE).then(cache=>cache.put("/index.html",response.clone())).catch(()=>{});
        return response;
      }catch{
        return (await caches.match("/index.html"))||Response.error();
      }
    })());
  }
});
