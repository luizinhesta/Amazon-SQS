const API_URL = "https://8ymj33o2il.execute-api.us-east-1.amazonaws.com";

const form = document.querySelector("#form-cadastro");
const btnCadastrar = document.querySelector("#btn-cadastrar");
const statusEl = document.querySelector("#status-cadastro");
const erroEl = document.querySelector("#erro-cadastro");
const sucessoEl = document.querySelector("#sucesso-cadastro");

function esconderTudo() {
  statusEl.classList.add("hidden");
  erroEl.classList.add("hidden");
  sucessoEl.classList.add("hidden");
}

function mostrarStatus(msg) {
  esconderTudo();
  statusEl.textContent = msg;
  statusEl.classList.remove("hidden");
}

function mostrarErro(msg) {
  esconderTudo();
  erroEl.textContent = msg;
  erroEl.classList.remove("hidden");
  btnCadastrar.disabled = false;
}

function mostrarSucesso(msg) {
  esconderTudo();
  sucessoEl.textContent = msg;
  sucessoEl.classList.remove("hidden");
  btnCadastrar.disabled = false;
}

function obterExtensao(arquivo) {
  const nome = arquivo.name.toLowerCase();
  if (nome.endsWith(".png")) return "png";
  if (nome.endsWith(".jpg") || nome.endsWith(".jpeg")) return "jpeg";
  if (nome.endsWith(".webp")) return "webp";
  return "png";
}

async function cadastrarProduto(dados) {
  const response = await fetch(`${API_URL}/produtos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  const resultado = await response.json();
  if (!response.ok) throw new Error(resultado.mensagem || "Erro ao cadastrar produto");
  return resultado;
}

async function uploadImagem(presignedUrl, arquivo, contentType) {
  const response = await fetch(presignedUrl, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: arquivo,
  });
  if (!response.ok) throw new Error("Falha ao enviar imagem para o S3");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (API_URL.includes("COLOCAR_URL")) {
    mostrarErro("Configure a constante API_URL no arquivo admin.js.");
    return;
  }

  const nome = document.querySelector("#nome").value.trim();
  const marca = document.querySelector("#marca").value.trim();
  const categoria = document.querySelector("#categoria").value.trim();
  const preco = parseFloat(document.querySelector("#preco").value);
  const unidade = document.querySelector("#unidade").value.trim();
  const imagemInput = document.querySelector("#imagem");
  const arquivo = imagemInput.files[0];

  if (!arquivo) {
    mostrarErro("Selecione uma imagem para o produto.");
    return;
  }

  if (arquivo.size > 3 * 1024 * 1024) {
    mostrarErro("A imagem deve ter no máximo 3 MB.");
    return;
  }

  btnCadastrar.disabled = true;
  const extensao = obterExtensao(arquivo);

  try {
    // 1. Cadastrar produto e obter presigned URL
    mostrarStatus("Cadastrando produto...");
    const resultado = await cadastrarProduto({ nome, marca, categoria, preco, unidade, extensao });

    // 2. Upload da imagem para o S3
    mostrarStatus("Enviando imagem para o S3...");
    await uploadImagem(resultado.upload_url, arquivo, `image/${extensao}`);

    mostrarSucesso(`Produto "${nome}" cadastrado com sucesso! Imagem salva no S3.`);
    form.reset();
  } catch (error) {
    mostrarErro(error.message || "Erro ao cadastrar produto.");
  }
});
