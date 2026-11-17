// Gera as legendas do vídeo real como PNGs transparentes 1080x1920.
// Uso: node legendas.js <pasta_de_saida>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const css = `
  * { margin: 0; box-sizing: border-box; }
  html, body { width: 1080px; height: 1920px; background: transparent; font-family: Inter, sans-serif; }
  .zona { position: absolute; left: 60px; right: 60px; top: 1130px; display: flex; flex-direction: column; align-items: center; gap: 18px; }
  .zona.alto { top: 230px; }
  .tarja { background: rgba(5,7,10,.86); color: #eef6f1; border-radius: 26px; padding: 22px 36px;
           font-weight: 800; font-size: 64px; line-height: 1.1; text-align: center;
           box-shadow: 0 0 0 4px #39ff88, 0 0 40px rgba(57,255,136,.55); }
  .grande { font-size: 104px; font-weight: 900; letter-spacing: -1px; color: #fff;
            text-shadow: 0 6px 0 #000, 0 0 30px rgba(0,0,0,.9), 0 0 60px rgba(57,255,136,.6); text-align: center; line-height: 1; }
  .verde { color: #39ff88; }
  .passo { display: flex; align-items: center; gap: 22px; }
  .num { width: 110px; height: 110px; border-radius: 50%; background: #39ff88; color: #05070a; font-weight: 900;
         font-size: 72px; display: grid; place-items: center; box-shadow: 0 0 40px rgba(57,255,136,.8); flex: none; }
  .fim { position: absolute; inset: 0; background: rgba(5,7,10,.72); display: flex; flex-direction: column;
         align-items: center; justify-content: center; gap: 34px; padding: 0 70px 260px; text-align: center; color: #eef6f1; }
  .logo { font-size: 120px; font-weight: 900; letter-spacing: -2px; }
  .logo span { color: #39ff88; text-shadow: 0 0 40px rgba(57,255,136,.7); }
  .sub { font-size: 54px; font-weight: 700; line-height: 1.2; }
  .preco { font-size: 150px; font-weight: 900; color: #39ff88; text-shadow: 0 0 50px rgba(57,255,136,.6); line-height: 1; }
  .preco small { font-size: 60px; color: #eef6f1; display: block; font-weight: 700; margin-bottom: 10px; }
  .chips { display: flex; gap: 18px; flex-wrap: wrap; justify-content: center; }
  .chip { border: 3px solid #22d3ee; color: #22d3ee; border-radius: 999px; padding: 12px 30px; font-size: 42px; font-weight: 800; }
  .cta { background: #39ff88; color: #05070a; border-radius: 26px; padding: 26px 60px; font-size: 66px; font-weight: 900;
         box-shadow: 0 0 50px rgba(57,255,136,.7); }
`;

const telas = {
  l1: `<div class="zona"><div class="grande">SUA TV <span class="verde">ANTIGA</span></div>
       <div class="tarja">tocando clipes o dia todo</div></div>`,
  l2: `<div class="zona"><div class="passo"><div class="num">1</div>
       <div class="tarja">Cole o link e clique<br>em <span class="verde">BAIXAR</span></div></div></div>`,
  l3: `<div class="zona"><div class="passo"><div class="num">2</div>
       <div class="tarja">Coloque o <span class="verde">pendrive</span><br>na TV</div></div></div>`,
  l4: `<div class="zona"><div class="passo"><div class="num">3</div>
       <div class="tarja">Escolha o vídeo<br>e dê <span class="verde">play</span></div></div></div>`,
  l5: `<div class="zona"><div class="grande verde">PRONTO!</div>
       <div class="tarja" style="white-space:nowrap;font-size:54px">Sem internet • Sem Smart TV</div></div>`,
  l6: `<div class="zona"><div class="tarja">Em casa, no salão<br>ou na <span class="verde">barbearia</span></div></div>`,
  fim: `<div class="fim">
       <div class="logo">Pendrive<span>Play</span></div>
       <div class="sub">Transforme sua TV antiga<br>em TV multimídia</div>
       <div class="chips"><div class="chip">Sem internet</div><div class="chip">Sem mensalidade</div></div>
       <div class="preco"><small>por apenas</small>R$ 19,90</div>
       <div class="cta">LINK NA BIO</div></div>`,
};

(async () => {
  const saida = process.argv[2] || path.join(__dirname, 'legendas');
  fs.mkdirSync(saida, { recursive: true });
  const nav = await chromium.launch();
  const pag = await nav.newPage({ viewport: { width: 1080, height: 1920 } });
  for (const [nome, html] of Object.entries(telas)) {
    await pag.setContent(`<!doctype html><meta charset="utf-8"><style>${css}</style><body>${html}</body>`);
    await pag.evaluate(() => document.fonts.ready);
    await pag.screenshot({ path: path.join(saida, nome + '.png'), omitBackground: true });
  }
  await nav.close();
  console.log('Legendas salvas em', saida);
})();
