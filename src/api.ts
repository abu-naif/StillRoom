export const CONNECTION_ERROR='Connection interrupted. Reconnecting… Check your internet and Tailscale connection.';
export class ConnectionError extends Error {constructor(){super(CONNECTION_ERROR);this.name='ConnectionError'}}
export async function api(path:string,data?:object){
 const body=data?JSON.stringify(data):undefined;
 const retryable=!data||path==='messages/send';
 for(let attempt=0;;attempt++){
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),data?30000:12000);
  try{
   const response=await fetch('/api/'+path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json','X-Stillroom':'1'}:{},body,keepalive:!!body&&new Blob([body]).size<60000,credentials:'same-origin',cache:'no-store',signal:controller.signal});
   if([502,503,504].includes(response.status))throw new ConnectionError();
   let result;try{result=await response.json()}catch{throw new Error('The server returned an invalid response. Please try again.')}
   if(!response.ok){if(response.status===401&&!['login','register','me'].includes(path))window.dispatchEvent(new Event('session-expired'));throw new Error(result.error||'Request failed.')}
   return result;
  }catch(error){
   const connection=error instanceof ConnectionError||error instanceof TypeError||(error as Error).name==='AbortError';
   if(!connection)throw error;
   if(!retryable||attempt>=1)throw new ConnectionError();
  }finally{clearTimeout(timeout)}
  await new Promise(resolve=>setTimeout(resolve,500));
 }
}
