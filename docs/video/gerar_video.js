// Gera o MP4 do vídeo explicativo a partir do video.html.
// Uso: node gerar_video.js [pasta_de_quadros] [saida.mp4] [quadros_por_segundo]
// Precisa do Playwright (Chromium) e do ffmpeg.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const pasta = process.argv[2] || path.join(__dirname, 'quadros');
  const saida = process.argv[3] || path.join(__dirname, 'PendrivePlay_video_vertical.mp4');
  const fps = Number(process.argv[4] || 30);
  fs.rmSync(pasta, { recursive: true, force: true });
  fs.mkdirSync(pasta, { recursive: true });

  const navegador = await chromium.launch();
  const pagina = await navegador.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await pagina.addInitScript(() => { window.MODO_GRAVACAO = true; });
  await pagina.goto('file://' + path.join(__dirname, 'video.html'));
  await pagina.evaluate(() => document.fonts.ready);
  await pagina.evaluate(() => Promise.all([...document.images].map(i => i.decode())));

  const duracao = await pagina.evaluate(() => window.DURACAO);
  const total = Math.round(duracao * fps);
  for (let q = 0; q < total; q++) {
    await pagina.evaluate((t) => window.render(t), q / fps);
    await pagina.screenshot({ path: path.join(pasta, String(q).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 92 });
    if (q % fps === 0) process.stdout.write(`\r${Math.round(q / total * 100)}%`);
  }
  await navegador.close();
  console.log(`\r${total} quadros gerados`);

  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(pasta, '%05d.jpg'),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', saida], { stdio: 'inherit' });
  console.log('Vídeo salvo em', saida);
})();
