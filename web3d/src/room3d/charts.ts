import * as THREE from 'three'
/** Dense vector-like canvas graphics replace the small photograph when a screen gets close. */
export function chartTexture(index:number):THREE.CanvasTexture {
 const canvas=document.createElement('canvas');canvas.width=2048;canvas.height=1152
 const c=canvas.getContext('2d')!,W=canvas.width,H=canvas.height
 c.fillStyle='#030914';c.fillRect(0,0,W,H)
 c.strokeStyle='#0d2036';c.lineWidth=2
 for(let x=40;x<W;x+=100){c.beginPath();c.moveTo(x,25);c.lineTo(x,H-40);c.stroke()}
 for(let y=30;y<H;y+=90){c.beginPath();c.moveTo(30,y);c.lineTo(W-35,y);c.stroke()}
 let seed=index+17;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}
 const bar=index%4===1||index%7===0
 if(bar){for(let i=0;i<170;i++){const x=45+i*(W-90)/170,h=(.08+rand()*.7)*H;c.fillStyle=i%3?'#165995':'#348ac2';c.fillRect(x,H-100-h,7,h)}}
 else{let p=H*.48;for(let i=0;i<320;i++){const open=p;p=THREE.MathUtils.clamp(p+(rand()-.49)*85,100,H-250);const x=40+i*(W-80)/320;c.strokeStyle=p<open?'#48a8d4':'#8971cd';c.lineWidth=2;c.beginPath();c.moveTo(x,Math.min(open,p)-rand()*30);c.lineTo(x,Math.max(open,p)+rand()*30);c.stroke();c.fillStyle=c.strokeStyle;c.fillRect(x-2,Math.min(open,p),4,Math.max(2,Math.abs(p-open)));c.fillStyle='#12324d';c.fillRect(x-2,H-85-rand()*100,4,rand()*100)}
 c.strokeStyle='#7566a5';c.lineWidth=2;c.beginPath();for(let i=0;i<200;i++){const x=40+i*(W-80)/200,y=H-160+Math.sin(i*.16+index)*35+rand()*12;i?c.lineTo(x,y):c.moveTo(x,y)}c.stroke()}
 c.fillStyle='#62829b';c.font='16px ui-monospace, monospace';for(let i=0;i<10;i++)c.fillText((i*10).toString(),W-40,80+i*(H-180)/10)
 const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.NoColorSpace;t.anisotropy=8
 return t
}

export function deskTexture():THREE.CanvasTexture {
 const canvas=document.createElement('canvas');canvas.width=2048;canvas.height=2048
 const c=canvas.getContext('2d')!,S=256,C=1024
 c.fillStyle='#030712';c.fillRect(0,0,2048,2048)
 c.translate(C,C)
 // The nine separate physical screen meshes supply the desk graphics.
 // This material is only the surrounding metal, rings and engraved seams.
 for(let i=0;i<18;i++){
  c.save();c.rotate(i*Math.PI/9);c.strokeStyle='#11253e';c.lineWidth=2
  c.beginPath();c.moveTo(0,-S*1.55);c.lineTo(0,-S*3.1);c.stroke();c.restore()
 }
 for(const [radius,color,width] of [[1.29,'#b47aff',5],[1.03,'#64d8ff',5],[.81,'#155992',2],[.65,'#134e7e',2],[.39,'#155a85',2],[.18,'#4acafa',3]] as [number,string,number][]){c.strokeStyle=color;c.lineWidth=width;c.beginPath();c.arc(0,0,radius*S,0,Math.PI*2);c.stroke()}
 for(let i=0;i<180;i++){const a=i*Math.PI/90;c.strokeStyle=i%5?'#123656':'#25628b';c.lineWidth=1;c.beginPath();c.moveTo(Math.cos(a)*S*1.22,Math.sin(a)*S*1.22);c.lineTo(Math.cos(a)*S*1.33,Math.sin(a)*S*1.33);c.stroke()}
 const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.NoColorSpace;t.anisotropy=8;return t
}
