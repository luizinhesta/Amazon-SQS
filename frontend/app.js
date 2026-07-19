const API_URL = "https://8ymj33o2il.execute-api.us-east-1.amazonaws.com";

const POLLING_INTERVAL_MS = 2000;
const MAX_POLLING_ATTEMPTS = 30;

const form = document.querySelector("#form-pesquisa");
const input = document.querySelector("#termo");
const btnPesquisar = form.querySelector("button[type='submit']");
const resultado = document.querySelector("#resultado");
const carregando = document.querySelector("#carregando");
const erro = document.querySelector("#erro");

function escapar(valor) {
  const el = document.createElement("div");
  el.textContent = String(valor ?? "");
  return el.innerHTML;
}

function moeda(valor) {
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function mostrarCarregando(mensagem) {
  carregando.textContent = mensagem || "Processando pesquisa...";
  carregando.classList.remove("hidden");
  erro.classList.add("hidden");
  resultado.classList.add("hidden");
  resultado.innerHTML = "";
}

function mostrarErro(mensagem) {
  carregando.classList.add("hidden");
  resultado.classList.add("hidden");
  erro.textContent = mensagem;
  erro.classList.remove("hidden");
  btnPesquisar.disabled = false;
}

function mostrarResultado(dados) {
  carregando.classList.add("hidden");
  erro.classList.add("hidden");
  resultado.classList.remove("hidden");
  btnPesquisar.disabled = false;

  if (dados.status === "NOT_FOUND") {
    resultado.innerHTML = `
      <div class="result-card not-found">
        <h3>Produto não encontrado</h3>
        <p>${escapar(dados.mensagem || "O produto pesquisado não existe no catálogo.")}</p>
        <p class="search-id">ID: ${escapar(dados.searchId)}</p>
      </div>`;
    return;
  }

  const imgSrc = dados.imagem_url || "";
  resultado.innerHTML = `
    <article class="result-card">
      ${imgSrc ? `<img src="${escapar(imgSrc)}" alt="${escapar(dados.nome)}" loading="lazy">` : ""}
      <div class="result-content">
        <p class="category">${escapar(dados.categoria)} · ${escapar(dados.marca)}</p>
        <h3>${escapar(dados.nome)}</h3>
        <div class="result-footer">
          <span class="price">${moeda(dados.preco)}</span>
          <span class="unit">${escapar(dados.unidade)}</span>
        </div>
        <p class="search-id">ID: ${escapar(dados.searchId)}</p>
      </div>
    </article>`;
}

async function criarPesquisa(produto) {
  const response = await fetch(`${API_URL}/pesquisas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ produto }),
  });
  const dados = await response.json();
  if (!response.ok) throw new Error(dados.mensagem || "Erro ao criar pesquisa");
  return dados;
}

async function consultarPesquisa(searchId) {
  const response = await fetch(`${API_URL}/pesquisas/${searchId}`);
  const dados = await response.json();
  if (!response.ok && response.status !== 404) {
    throw new Error(dados.mensagem || "Erro ao consultar pesquisa");
  }
  return dados;
}

function aguardar(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function iniciarPolling(searchId) {
  for (let tentativa = 1; tentativa <= MAX_POLLING_ATTEMPTS; tentativa++) {
    mostrarCarregando(`Processando... (${tentativa}/${MAX_POLLING_ATTEMPTS})`);
    await aguardar(POLLING_INTERVAL_MS);

    const dados = await consultarPesquisa(searchId);

    if (dados.status === "COMPLETED" || dados.status === "NOT_FOUND") {
      mostrarResultado(dados);
      return;
    }
  }

  mostrarErro("Tempo esgotado. A pesquisa ainda está sendo processada.");
}

async function pesquisar(produto) {
  if (API_URL.includes("COLOCAR_URL")) {
    mostrarErro("Configure a constante API_URL no arquivo app.js.");
    return;
  }

  btnPesquisar.disabled = true;
  mostrarCarregando("Enviando pesquisa...");

  try {
    const { searchId } = await criarPesquisa(produto);
    await iniciarPolling(searchId);
  } catch (error) {
    mostrarErro(error.message || "Não foi possível realizar a pesquisa.");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const termo = input.value.trim();
  if (!termo) {
    mostrarErro("Informe o nome do produto para pesquisar.");
    return;
  }
  pesquisar(termo);
});
