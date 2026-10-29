/* Agente Empresarial · interface da demo.
   Ao vivo: POST /api/conversas/{id}/mensagens devolve um fluxo SSE com cada etapa do agente
   ("rodando" ao começar, "feito"/"falhou" ao terminar) e, no fim, o turno completo.
   Reprodução: as mesmas etapas lidas do log, no ritmo em que aconteceram, sem chamar API. */

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...filhos) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) if (f !== null && f !== undefined) n.append(f.nodeType ? f : document.createTextNode(f));
  return n;
};

const estado = {
  sessao: null,
  cliente: null,
  ocupado: false,
  reproduzindo: false,
  clausulas: {},
  ultimoTurno: null,
};

const SVG = {
  marca:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="6" fill="var(--marca)"/><path d="M12 5l6 2.4v4.3c0 3.6-2.5 6.3-6 7.3-3.5-1-6-3.7-6-7.3V7.4z" fill="var(--primary)"/></svg>',
  rodando: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5a5.5 5.5 0 1 1-5.5 5.5"/></svg>',
  feito: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.2"/><path d="M5.4 8.2l1.8 1.8 3.4-3.6"/></svg>',
  falhou: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.2"/><path d="M6 6l4 4M10 6l-4 4"/></svg>',
  seta: '<svg class="seta" viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5L8 6l-3.5 3.5"/></svg>',
};

/* ---------- formatação ---------- */
const segundos = (s) => `${(s ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;
const pct = (p) => `${Math.round(p * 100)}%`;
function reais(v) {
  if (v >= 1e6) return `R$ ${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (v >= 1e3) return `R$ ${Math.round(v / 1e3).toLocaleString("pt-BR")} mil`;
  return `R$ ${Math.round(v).toLocaleString("pt-BR")}`;
}
function faixa(min, max) {
  const [a, b] = [reais(min), reais(max)];
  if (a === b) return a;
  const unidade = (s) => s.split(" ").at(-1);
  return unidade(a) === unidade(b) ? `${a.replace(/ (mil|mi)$/, "")} a ${b.replace("R$ ", "")}` : `${a} a ${b.replace("R$ ", "")}`;
}
const PLANO = { ESSENCIAL: "Essencial", PRATICO: "Prático", TOTAL: "Total" };
const nomePlano = (p) => PLANO[p] ?? p ?? "Sem plano";
const INTENCAO = {
  responder_pergunta: "Responde à pergunta",
  perguntar_cobertura: "Pergunta sobre cobertura",
  objecao: "Objeção",
  quer_contratar: "Quer contratar",
  sem_interesse: "Sem interesse",
  outro: "Outro assunto",
};
const CONFIRMACAO = { sim: "Sim", nao: "Não", nao_sabe: "Não sabe", nao_respondeu: "Não respondeu" };

/* Rótulo curto de uma cláusula para o texto ("Frigorificados 1.1 a"); o id completo fica no popover. */
const COBERTURA_CURTA = {
  INCENDIO_RAIO_EXPLOSAO_FUMACA: "Incêndio", DANOS_ELETRICOS: "Danos elétricos", PERDA_PAGAMENTO_ALUGUEL: "Aluguel",
  RESPONSABILIDADE_CIVIL_ESTABELECIMENTO: "RC estabelecimento", RESPONSABILIDADE_CIVIL_EMPREGADOR: "RC empregador",
  RESPONSABILIDADE_CIVIL_DISPOSICOES_GERAIS: "RC geral", DESPESAS_FIXAS: "Despesas fixas", ROUBO_FURTO_ARROMBAMENTO: "Roubo",
  VENDAVAL_EVENTOS_CORRELATOS: "Vendaval", QUEBRA_DE_VIDROS: "Vidros", DELIVERY: "Delivery",
  DETERIORACAO_DE_MERCADORIAS_EM_AMBIENTES_FRIGORIFICADOS: "Frigorificados",
  ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO: "Valores", CG: "CG",
};
function rotuloCurto(id) {
  const i = id.indexOf("-");
  if (i < 0) return id;
  const [prefixo, resto] = [id.slice(0, i), id.slice(i + 1)];
  if (prefixo === "PLANO") return `Plano ${nomePlano(resto)}`;
  if (prefixo === "SITE") return "BB Seguros: cibernética";
  if (prefixo === "TT") return `Termo: ${resto.toLowerCase().replaceAll("_", " ")}`;
  const nome = COBERTURA_CURTA[prefixo] ?? prefixo.toLowerCase().replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
  return `${nome} ${resto.replace(/\.([a-z])(-\d)?$/, " $1$2")}`;
}
const encurtarIds = (texto) => texto.replace(/\b[A-Z][A-Z_]*-[0-9A-Z][\w.-]*/g, (id) => rotuloCurto(id));


function escapar(t) {
  return t.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/* Texto do agente: parágrafos, listas com "- ", **negrito** e citações [cl. ID] clicáveis. */
function renderizarTexto(texto) {
  const linhas = escapar(texto).split(/\n/);
  const blocos = [];
  let lista = null;
  for (const linha of linhas) {
    const item = linha.match(/^\s*[-•]\s+(.*)/);
    if (item) {
      lista ??= [];
      lista.push(item[1]);
      continue;
    }
    if (lista) { blocos.push(`<ul>${lista.map((i) => `<li>${i}</li>`).join("")}</ul>`); lista = null; }
    if (linha.trim()) blocos.push(`<p>${linha}</p>`);
  }
  if (lista) blocos.push(`<ul>${lista.map((i) => `<li>${i}</li>`).join("")}</ul>`);
  return blocos
    .join("")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[cl\.\s*([^\]]+?)\s*\]/g, (_, id) => `<button type="button" class="cit" data-id="${id}" aria-expanded="false" aria-label="Ver cláusula ${id}">${rotuloCurto(id)}</button>`);
}

/* ---------- mensagens ---------- */
const mensagens = $("#mensagens");
function rolar() { mensagens.scrollTop = mensagens.scrollHeight; }

function adicionarCliente(texto) {
  mensagens.append(el("article", { class: "msg cliente", "aria-label": "Mensagem do cliente" }, el("p", { class: "balao" }, texto)));
  rolar();
}

/* Um turno do agente: o bloco de raciocínio (etapas ao vivo) e, depois, a resposta. */
function novoTurnoAgente() {
  const resumoTexto = el("span", { class: "resumo-texto" }, "Pensando");
  const tempo = el("span", { class: "tempo num" }, segundos(0));
  const lista = el("ol", { class: "etapas", "aria-label": "Etapas do agente" });
  const detalhes = el("details", { class: "raciocinio ativo", open: true },
    el("summary", { html: SVG.seta }, resumoTexto, tempo), lista);
  const corpo = el("div", { class: "texto" });
  const artigo = el("article", { class: "msg agente", "aria-label": "Resposta do agente" },
    el("p", { class: "autor", html: `${SVG.marca}<span>Agente Empresarial</span>` }), detalhes, corpo);
  mensagens.append(artigo);
  rolar();

  const inicio = performance.now();
  const relogio = setInterval(() => { tempo.textContent = segundos((performance.now() - inicio) / 1000); }, 100);
  const itens = new Map();

  return {
    etapa(ev) {
      let li = itens.get(ev.id);
      if (!li) {
        li = el("li", { class: "etapa" },
          el("span", { class: "icone" }), el("p", { class: "et-titulo" }), el("span", { class: "et-tempo num" }), el("p", { class: "et-detalhe" }));
        itens.set(ev.id, li);
        lista.append(li);
      }
      li.className = `etapa ${ev.estado}`;
      li.querySelector(".icone").innerHTML = SVG[ev.estado] ?? SVG.feito;
      li.querySelector(".et-titulo").textContent = ev.titulo;
      li.querySelector(".et-tempo").textContent = ev.estado === "rodando" ? "" : ev.segundos != null ? segundos(ev.segundos) : "";
      const det = li.querySelector(".et-detalhe");
      det.textContent = ev.detalhe ? encurtarIds(ev.detalhe) : "";
      det.hidden = !ev.detalhe;
      if (ev.estado === "rodando") resumoTexto.textContent = ev.titulo;
      rolar();
    },
    concluir(turno) {
      clearInterval(relogio);
      detalhes.classList.remove("ativo");
      const n = itens.size;
      resumoTexto.textContent = `Pensou por ${segundos(turno.segundos)}`;
      tempo.textContent = `· ${n} etapas`;
      setTimeout(() => { detalhes.open = false; }, 700);
      corpo.innerHTML = renderizarTexto(turno.resposta);
      if (turno.requer_humano) corpo.classList.add("encaminhado");
      rolar();
    },
    falhar(mensagem) {
      clearInterval(relogio);
      detalhes.classList.remove("ativo");
      resumoTexto.textContent = "O turno falhou";
      corpo.append(el("p", { class: "erro-turno" }, mensagem, " ", el("button", { class: "botao secundario", type: "button", onclick: () => reenviar() }, "Tentar de novo")));
      rolar();
    },
  };
}

/* ---------- painel do plano personalizado ---------- */
function renderizarDetalhes(cliente, turno) {
  const p = (turno && turno.personalizado) || cliente.personalizado;
  const alvo = $("#detalhes-conteudo");
  alvo.replaceChildren();
  if (!p) return;

  const mudou = turno && turno.plano_anterior && turno.plano && turno.plano_anterior !== turno.plano;
  const eleg = p.elegivel === "SIM"
    ? el("span", { class: "pilula positiva" }, "Elegível")
    : el("span", { class: "pilula aviso", title: p.motivo_elegibilidade || "" }, "Elegibilidade a confirmar");
  const conf = el("span", { class: `pilula${p.confianca_geral === "BAIXA" ? " aviso" : ""}` }, `Confiança ${p.confianca_geral.toLowerCase().replace("media", "média")}`);
  alvo.append(el("section", { class: "bloco" },
    el("h2", {}, "Plano recomendado"),
    el("p", { class: "plano-nome" }, nomePlano(p.plano_base)),
    mudou ? el("p", { class: "plano-mudanca", html: `Era ${escapar(nomePlano(turno.plano_anterior))}; mudou para <strong>${escapar(nomePlano(turno.plano))}</strong> com a resposta do cliente.` }) : null,
    el("div", { class: "metas" }, eleg, conf, el("span", { class: "pilula" }, p.relacao_imovel === "LOCATARIO" ? "Imóvel alugado" : "Imóvel provavelmente próprio")),
  ));

  const pergunta = turno ? turno.proxima_pergunta : cliente.pergunta_pendente;
  if (pergunta) {
    alvo.append(el("section", { class: "bloco" },
      el("div", { class: "pergunta-pendente" }, el("p", {}, "A pergunta que decide o plano"), el("p", {}, pergunta))));
  }

  const linha = (c, adicional) => el("li", { class: `cobertura${adicional ? " adicional" : ""}${c.confianca === "BAIXA" ? " cob-baixa" : ""}`, title: c.justificativa },
    el("span", { class: "cob-nome" }, c.nome),
    el("span", { class: "cob-faixa num" }, faixa(c.minimo, c.maximo)),
    adicional ? el("span", { class: "cob-sub" }, c.justificativa.split(";")[0]) : null);

  const fixas = p.coberturas.filter((c) => c.origem === "plano");
  const adicionais = p.coberturas.filter((c) => c.origem === "adicional");
  if (adicionais.length) {
    alvo.append(el("section", { class: "bloco" },
      el("h2", {}, `Adicionais para este negócio (${adicionais.length})`),
      el("ul", { class: "coberturas" }, adicionais.map((c) => linha(c, true)))));
  }
  alvo.append(el("section", { class: "bloco" },
    el("h2", {}, `Coberturas do plano ${nomePlano(p.plano_base)} (${fixas.length})`),
    fixas.length ? el("ul", { class: "coberturas" }, fixas.map((c) => linha(c, false)))
      : el("p", { class: "vazio-bloco" }, "Plano suspenso: faltam dados essenciais no cadastro."),
    el("p", { class: "legenda" }, "Faixas sugeridas de limite de indenização, a confirmar. Não são preço.")));

  if (p.dados_a_conferir && p.dados_a_conferir.length) {
    alvo.append(el("section", { class: "bloco" },
      el("h2", {}, "Dados do cadastro a conferir"),
      el("ul", { class: "conferir" }, p.dados_a_conferir.map((d) => el("li", {}, d[0].toUpperCase() + d.slice(1))))));
  }

  const blocoTurno = el("section", { class: "bloco" }, el("h2", {}, "Decisões do último turno"));
  if (!turno) {
    blocoTurno.append(el("p", { class: "vazio-bloco" }, "Aparecem aqui quando o cliente escrever: intenção, confirmação, rota e guardrail."));
  } else {
    const d = turno.decisoes;
    const linhaDecisao = (rotulo, valor, prob) => [
      el("dt", {}, rotulo), el("dd", { class: "num" }, `${valor} · ${pct(prob)}`),
      el("div", { class: "barra", "aria-hidden": "true" }, el("span", { style: `width:${Math.round(prob * 100)}%` })),
    ];
    const lista = el("dl", { class: "decisoes" });
    const add = (...partes) => lista.append(el("div", { class: "decisao" }, ...partes));
    if (d.intencao) add(...linhaDecisao("Intenção", INTENCAO[d.intencao.valor] ?? d.intencao.valor, d.intencao.probabilidade));
    if (d.confirmacao) add(...linhaDecisao("Confirmação", CONFIRMACAO[d.confirmacao.valor] ?? d.confirmacao.valor, d.confirmacao.probabilidade));
    if (d.rota) add(...linhaDecisao("Rota", d.rota.valor === "gerente" ? "Gerente" : "Agente", d.rota.probabilidade));
    const g = turno.guardrail;
    add(el("dt", {}, "Guardrail"), el("dd", {},
      g && g.aprovado ? el("span", { class: "pilula positiva" }, g.tentativas > 1 ? "Aprovado na reescrita" : "Aprovado")
        : el("span", { class: "pilula negativa", title: g ? g.motivo : "" }, "Reprovado")));
    blocoTurno.append(lista);
    if (turno.requer_humano) {
      blocoTurno.append(el("p", { class: "conferir", style: "margin-top:10px" }, el("li", {}, `Encaminhado ao gerente: ${turno.motivo_humano}`)));
    }
  }
  alvo.append(blocoTurno);
}

/* ---------- popover de cláusula ---------- */
const popover = $("#popover");
let citacaoAberta = null;
function fecharPopover() {
  popover.hidden = true;
  if (citacaoAberta) citacaoAberta.setAttribute("aria-expanded", "false");
  citacaoAberta = null;
}
mensagens.addEventListener("click", (e) => {
  const botao = e.target.closest(".cit");
  if (!botao) return;
  e.stopPropagation();
  if (citacaoAberta === botao) return fecharPopover();
  fecharPopover();
  const c = estado.clausulas[botao.dataset.id];
  popover.replaceChildren(
    el("p", { class: "pop-id" }, botao.dataset.id),
    el("p", { class: "pop-secao" }, c ? `${c.secao}${c.pagina ? ` · pág. ${c.pagina}` : ""}` : "Cláusula não encontrada neste turno"),
    c ? el("p", { class: "pop-texto" }, c.texto) : null,
  );
  popover.hidden = false;
  const r = botao.getBoundingClientRect();
  const largura = popover.offsetWidth;
  popover.style.left = `${Math.max(16, Math.min(r.left, innerWidth - largura - 16))}px`;
  const abaixo = r.bottom + 8;
  popover.style.top = abaixo + popover.offsetHeight > innerHeight - 16 ? `${Math.max(16, r.top - popover.offsetHeight - 8)}px` : `${abaixo}px`;
  botao.setAttribute("aria-expanded", "true");
  citacaoAberta = botao;
});
document.addEventListener("click", (e) => { if (!popover.contains(e.target)) fecharPopover(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharPopover(); });
mensagens.addEventListener("scroll", fecharPopover);

/* ---------- cliente e conversa ---------- */
function definirModo(reproducao, texto) {
  const modo = $("#modo");
  modo.className = `modo ${reproducao ? "reproducao" : "ao-vivo"}`;
  $("#modo-texto").textContent = texto ?? (reproducao ? "Reprodução" : "Ao vivo");
}

function mostrarCliente(cliente, subtitulo) {
  estado.cliente = cliente;
  $("#titulo").textContent = cliente.segmento;
  $("#cliente-id").textContent = cliente.cliente_id;
  $("#escopo-cliente").textContent = `${cliente.segmento} · ${cliente.empresa_id}`;
  $("#subtitulo").innerHTML = subtitulo ?? (cliente.plano
    ? `Pelo cadastro, o motor indica o plano <strong>${escapar(nomePlano(cliente.plano))}</strong>${cliente.pergunta_pendente ? ", e uma resposta do cliente pode mudar isso." : "."} Escreva como o cliente para ver o agente decidir.`
    : "O cadastro deste cliente está incompleto: o motor suspendeu a indicação até confirmar os dados.");
  renderizarDetalhes(cliente, null);
  const chips = () => cliente.sugestoes.map((s, i) =>
    el("button", { type: "button", class: `sugestao${i === 0 && cliente.pergunta_pendente ? " destaque" : ""}`, onclick: () => enviar(s) }, s));
  $("#sugestoes").replaceChildren(...chips());
  $("#sugestoes").hidden = true; // na primeira tela as sugestões ficam na introdução
  if (!mensagens.children.length) {
    mensagens.append(el("section", { class: "intro", "aria-labelledby": "intro-titulo" },
      el("h2", { id: "intro-titulo" }, "O que o agente já sabe pelo cadastro"),
      el("dl", { class: "fatos" }, cliente.fatos.map((f) => el("div", { class: "fato" }, el("dt", {}, f.rotulo), el("dd", { class: "num" }, f.valor)))),
      el("p", { class: "achado" }, cliente.achado),
      estado.reproduzindo ? null : el("p", { class: "achado-rotulo" }, "Comece escrevendo como o cliente, ou use um exemplo:"),
      estado.reproduzindo ? null : el("div", { class: "sugestoes-intro" }, chips())));
  }
  document.querySelectorAll(".nav-item[data-cliente]").forEach((b) => b.setAttribute("aria-current", String(b.dataset.cliente === cliente.cliente_id)));
}

async function abrirCliente(clienteId) {
  if (estado.ocupado) return;
  estado.reproduzindo = false;
  definirModo(false);
  fecharMenu();
  mensagens.replaceChildren();
  estado.clausulas = {};
  $("#titulo").textContent = "Abrindo cliente…";
  const r = await fetch("/api/conversas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cliente_id: clienteId }) });
  if (!r.ok) { $("#subtitulo").textContent = "Não foi possível abrir este cliente."; return; }
  const dados = await r.json();
  estado.sessao = dados.sessao_id;
  mostrarCliente(dados.cliente);
  bloquear(false);
  $("#entrada").focus();
}

function bloquear(sim) {
  estado.ocupado = sim;
  $("#enviar").disabled = sim || estado.reproduzindo;
  $("#entrada").disabled = estado.reproduzindo;
  document.querySelectorAll(".sugestao").forEach((b) => { b.disabled = sim || estado.reproduzindo; });
}

/* Lê o fluxo SSE do POST e chama cada(tipo, dados) a cada evento. */
async function lerEventos(resposta, cada) {
  const leitor = resposta.body.getReader();
  const dec = new TextDecoder();
  let resto = "";
  for (;;) {
    const { value, done } = await leitor.read();
    if (done) break;
    resto += dec.decode(value, { stream: true });
    let fim;
    while ((fim = resto.indexOf("\n\n")) >= 0) {
      const bloco = resto.slice(0, fim);
      resto = resto.slice(fim + 2);
      const tipo = bloco.match(/^event: (.*)$/m)?.[1];
      const dados = bloco.match(/^data: (.*)$/m)?.[1];
      if (tipo && dados) cada(tipo, JSON.parse(dados));
    }
  }
}

let ultimaMensagem = "";
async function enviar(texto) {
  texto = texto.trim();
  if (!texto || estado.ocupado || estado.reproduzindo || !estado.sessao) return;
  ultimaMensagem = texto;
  $("#sugestoes").hidden = false;
  mensagens.querySelector(".sugestoes-intro")?.remove();
  mensagens.querySelector(".achado-rotulo")?.remove();
  $("#entrada").value = "";
  ajustarAltura();
  bloquear(true);
  adicionarCliente(texto);
  const turno = novoTurnoAgente();
  try {
    const r = await fetch(`/api/conversas/${estado.sessao}/mensagens`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto }),
    });
    if (!r.ok) throw new Error((await r.json()).detail ?? `erro ${r.status}`);
    await lerEventos(r, (tipo, dados) => {
      if (tipo === "etapa") turno.etapa(dados);
      else if (tipo === "turno") {
        Object.assign(estado.clausulas, dados.clausulas);
        turno.concluir(dados);
        estado.ultimoTurno = dados;
        renderizarDetalhes(estado.cliente, dados);
        atualizarSubtitulo(dados);
      } else if (tipo === "erro") turno.falhar(dados.mensagem);
    });
  } catch (erro) {
    turno.falhar(`Sem resposta do servidor (${erro.message}).`);
  } finally {
    bloquear(false);
    $("#entrada").focus();
  }
}
function atualizarSubtitulo(turno) {
  if (turno.plano && turno.plano_anterior && turno.plano !== turno.plano_anterior) {
    $("#subtitulo").innerHTML = `O plano mudou de ${escapar(nomePlano(turno.plano_anterior))} para <strong>${escapar(nomePlano(turno.plano))}</strong> com a resposta do cliente.`;
  }
}
function reenviar() { if (ultimaMensagem) enviar(ultimaMensagem); }

/* ---------- reprodução a partir do log ---------- */
const esperar = (ms) => new Promise((ok) => setTimeout(ok, ms));
/* Os mesmos títulos "em andamento" que o pipeline manda ao vivo. */
const TITULO_RODANDO = {
  decidir: "Interpretando a mensagem com o Jev",
  objecao: "Identificando a objeção do cliente",
  regras: "Recalculando o plano no motor de score",
  recuperar: "Consultando as Condições Gerais",
  redigir: "Redigindo a resposta com o Claude Haiku",
  conferir: "Conferindo citações e promessas",
  reescrever: "Reescrevendo a resposta",
  conferir_2: "Conferindo de novo",
};
async function reproduzir(sessaoId) {
  if (estado.ocupado) return;
  fecharMenu();
  const r = await fetch(`/api/gravacoes/${sessaoId}`);
  if (!r.ok) return;
  const g = await r.json();
  estado.reproduzindo = true;
  estado.sessao = null;
  estado.clausulas = {};
  definirModo(true, `Reprodução · sessão ${sessaoId}`);
  mensagens.replaceChildren();
  mostrarCliente(g.cliente, `Reprodução da sessão <strong>${escapar(sessaoId)}</strong>, lida do log de auditoria: nenhuma API é chamada.`);
  $("#sugestoes").replaceChildren();
  bloquear(true);
  for (const t of g.turnos) {
    adicionarCliente(t.mensagem);
    await esperar(500);
    const turno = novoTurnoAgente();
    for (const e of t.etapas) {
      turno.etapa({ ...e, estado: "rodando", titulo: TITULO_RODANDO[e.id] ?? e.titulo, detalhe: null, segundos: null });
      await esperar(Math.min(Math.max((e.segundos ?? 0) * 1000, 250), 2200));
      turno.etapa(e);
    }
    Object.assign(estado.clausulas, t.clausulas);
    turno.concluir(t);
    renderizarDetalhes(g.cliente, t);
    await esperar(1200);
  }
  estado.ocupado = false;
  definirModo(true, `Reprodução concluída · sessão ${sessaoId}`);
}

async function carregarGravacoes() {
  const lista = $("#lista-gravacoes");
  lista.replaceChildren(el("li", { class: "vazio" }, "Carregando…"));
  const g = await (await fetch("/api/gravacoes")).json();
  if (!g.length) { lista.replaceChildren(el("li", { class: "vazio" }, "Nenhuma conversa gravada ainda.")); return; }
  lista.replaceChildren(...g.map((s) => el("li", {},
    el("button", { class: "nav-item", type: "button", onclick: () => reproduzir(s.sessao_id) },
      el("span", { class: "nav-texto" },
        el("span", { class: "nav-titulo" }, s.primeira_mensagem),
        el("span", { class: "nav-sub" }, `${s.cliente_id.replace("IMO_", "")} · ${s.turnos} ${s.turnos === 1 ? "turno" : "turnos"}`))))));
}

/* ---------- navegação, menu e inicialização ---------- */
function fecharMenu() { $("#lateral").classList.remove("aberta"); }
$("#abrir-menu").addEventListener("click", () => $("#lateral").classList.add("aberta"));
$("#fechar-menu").addEventListener("click", fecharMenu);
$("#ver-plano").addEventListener("click", () => { $("#detalhes").classList.add("aberto"); $("#ver-plano").setAttribute("aria-expanded", "true"); });
$("#fechar-detalhes").addEventListener("click", () => { $("#detalhes").classList.remove("aberto"); $("#ver-plano").setAttribute("aria-expanded", "false"); });
$("#nova").addEventListener("click", () => estado.cliente && abrirCliente(estado.cliente.cliente_id));
$("#abrir-gravacoes").addEventListener("click", () => {
  const lista = $("#lista-gravacoes");
  const abrir = lista.hidden;
  lista.hidden = !abrir;
  $("#abrir-gravacoes").setAttribute("aria-expanded", String(abrir));
  if (abrir) carregarGravacoes();
});
$("#outro-cliente").addEventListener("change", (e) => e.target.value && abrirCliente(e.target.value));

const entrada = $("#entrada");
function ajustarAltura() { entrada.style.height = "auto"; entrada.style.height = `${Math.min(entrada.scrollHeight, 160)}px`; }
entrada.addEventListener("input", ajustarAltura);
entrada.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(entrada.value); }
});
$("#compositor").addEventListener("submit", (e) => { e.preventDefault(); enviar(entrada.value); });

async function iniciar() {
  const [clientes, saude] = await Promise.all([
    fetch("/api/clientes").then((r) => r.json()),
    fetch("/api/saude").then((r) => r.json()).catch(() => null),
  ]);
  $("#lista-personas").replaceChildren(...clientes.personas.map((p) => el("li", {},
    el("button", { class: "nav-item", type: "button", "data-cliente": p.cliente_id, onclick: () => abrirCliente(p.cliente_id) },
      el("span", { class: "nav-texto" },
        el("span", { class: "nav-titulo" }, p.segmento),
        el("span", { class: "nav-sub" }, p.tem_pergunta ? "Fronteira: 1 pergunta decide" : "Caso claro")),
      el("span", { class: "plano-tag" }, nomePlano(p.plano))))));
  $("#outro-cliente").replaceChildren(el("option", { value: "" }, `Escolher entre ${clientes.todos.length}`),
    ...clientes.todos.map((id) => el("option", { value: id }, id.replace("IMO_", ""))));
  if (saude) {
    $("#saude-texto").textContent = `${saude.decisor} · busca ${saude.busca}`;
    $("#saude").querySelector(".saude-linha").classList.add("ok");
  }
  const fronteira = clientes.personas.find((p) => p.tem_pergunta) ?? clientes.personas[0];
  abrirCliente(fronteira.cliente_id);
}
iniciar();
