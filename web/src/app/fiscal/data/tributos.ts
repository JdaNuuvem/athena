import type { TributoRecord } from "../types";

const TRIBUTOS = ["ICMS", "IPI", "PIS", "COFINS", "ISS", "ST", "DIFAL"];
const MESES = ["2026-05", "2026-06", "2026-07"];

const ALIQUOTAS: Record<string, string> = { ICMS: "18%", IPI: "10%", PIS: "1,65%", COFINS: "7,6%", ISS: "5%", ST: "12%", DIFAL: "7%" };
const BASES: Record<string, number> = { ICMS: 45000, IPI: 30000, PIS: 50000, COFINS: 50000, ISS: 15000, ST: 25000, DIFAL: 20000 };

export function gerarTributosMock(): TributoRecord[] {
  return MESES.flatMap((mes, mi) =>
    TRIBUTOS.map((tributo, ti) => {
      const id = mi * TRIBUTOS.length + ti + 1;
      const base = BASES[tributo] * (1 + mi * 0.05);
      const aliquotaNum = parseFloat(ALIQUOTAS[tributo].replace(",", ".").replace("%", ""));
      const valor = base * (aliquotaNum / 100);
      return {
        id,
        tributo,
        apuracao: mes,
        baseCalculo: base,
        aliquota: ALIQUOTAS[tributo],
        valor,
        vencimento: mi === 2
          ? `2026-08-${String(15 + ti).padStart(2, "0")}`
          : `2026-${String(6 + mi).padStart(2, "0")}-${String(15 + ti).padStart(2, "0")}`,
        status: (mi === 2 ? "pendente" : "pago") as "pago" | "pendente",
      };
    })
  );
}
