// Divide um total de unidades de estoque entre lojas, proporcional a demanda
// de cada uma (unidades vendidas do SKU no periodo — ver
// core/relatorios.py::demanda_por_loja). Cada loja recebe um piso minimo
// garantido (mesmo sem venda no periodo); o restante e' rateado
// proporcionalmente entre quem tem demanda > 0.

export interface LojaComDemanda {
  chave: string; // identificador estavel (ex: nome da loja no EstoqueMultiLojaModal)
  demanda: number;
}

export function dividirPorDemanda(
  total: number,
  lojas: LojaComDemanda[],
  pisoMinimo = 1
): Record<string, number> {
  const resultado: Record<string, number> = {};
  if (lojas.length === 0 || total <= 0) {
    lojas.forEach((l) => { resultado[l.chave] = 0; });
    return resultado;
  }

  // Total menor que o numero de lojas: nao da pra garantir o piso pra
  // todo mundo — prioriza quem tem mais demanda ate esgotar o total.
  if (total < lojas.length * pisoMinimo) {
    lojas.forEach((l) => { resultado[l.chave] = 0; });
    const ordenadas = [...lojas].sort((a, b) => b.demanda - a.demanda);
    let restante = total;
    for (const l of ordenadas) {
      if (restante <= 0) break;
      const dar = Math.min(pisoMinimo, restante);
      resultado[l.chave] = dar;
      restante -= dar;
    }
    return resultado;
  }

  lojas.forEach((l) => { resultado[l.chave] = pisoMinimo; });
  let restante = total - lojas.length * pisoMinimo;

  const somaDemanda = lojas.reduce((s, l) => s + Math.max(l.demanda, 0), 0);
  if (somaDemanda <= 0) {
    // Ninguem vendeu — divide o restante igualmente, sobra pra primeira loja.
    const porLoja = Math.floor(restante / lojas.length);
    lojas.forEach((l) => { resultado[l.chave] += porLoja; });
    const sobra = restante - porLoja * lojas.length;
    if (sobra > 0 && lojas[0]) resultado[lojas[0].chave] += sobra;
    return resultado;
  }

  // Rateio proporcional com piso em floor() — a sobra do arredondamento
  // (sempre < numero de lojas com demanda) vai pra quem tem maior demanda.
  let distribuido = 0;
  const comDemanda = lojas.filter((l) => l.demanda > 0);
  comDemanda.forEach((l) => {
    const fatia = Math.floor((restante * l.demanda) / somaDemanda);
    resultado[l.chave] += fatia;
    distribuido += fatia;
  });
  const sobra = restante - distribuido;
  if (sobra > 0 && comDemanda.length > 0) {
    const maiorDemanda = [...comDemanda].sort((a, b) => b.demanda - a.demanda)[0];
    resultado[maiorDemanda.chave] += sobra;
  }
  return resultado;
}
