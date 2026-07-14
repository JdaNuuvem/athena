import type { CfopRecord, NcmRecord, CestRecord, IbptRecord } from "../types";

export const CFOP_DATA: CfopRecord[] = [
  { codigo: "5.101", descricao: "Venda de produção do estabelecimento", tipo: "Saída" },
  { codigo: "5.102", descricao: "Venda de mercadoria adquirida ou recebida de terceiros", tipo: "Saída" },
  { codigo: "5.403", descricao: "Venda de mercadoria adquirida ou recebida de terceiros em operação com mercadoria sujeita ao regime de ST", tipo: "Saída" },
  { codigo: "5.405", descricao: "Venda de mercadoria, adquirida ou recebida de terceiros em operação com mercadoria sujeita ao regime de ST", tipo: "Saída" },
  { codigo: "6.101", descricao: "Venda de produção do estabelecimento para outros estados", tipo: "Saída" },
  { codigo: "6.102", descricao: "Venda de mercadoria adquirida para outros estados", tipo: "Saída" },
  { codigo: "1.101", descricao: "Compra para industrialização", tipo: "Entrada" },
  { codigo: "1.102", descricao: "Compra para comercialização", tipo: "Entrada" },
  { codigo: "1.403", descricao: "Compra para comercialização em operação com mercadoria sujeita ao regime de ST", tipo: "Entrada" },
  { codigo: "1.949", descricao: "Outra entrada de mercadoria ou prestação de serviço não especificada", tipo: "Entrada" },
];

export const NCM_DATA: NcmRecord[] = [
  { codigo: "8471.30.19", descricao: "Outras máquinas automáticas para processamento de dados, portáteis", aliquotaIPI: "0%", aliquotaNacional: "0%" },
  { codigo: "8517.12.31", descricao: "Telefones inteligentes (smartphones)", aliquotaIPI: "2%", aliquotaNacional: "12%" },
  { codigo: "8528.72.00", descricao: "Aparelhos receptores de televisão, a cores", aliquotaIPI: "10%", aliquotaNacional: "20%" },
  { codigo: "9403.60.00", descricao: "Móveis de madeira para escritório", aliquotaIPI: "5%", aliquotaNacional: "12%" },
  { codigo: "6109.10.00", descricao: "Camisetas de algodão", aliquotaIPI: "0%", aliquotaNacional: "7%" },
  { codigo: "2203.00.00", descricao: "Cervejas de malte", aliquotaIPI: "40%", aliquotaNacional: "25%" },
  { codigo: "3304.99.90", descricao: "Outros produtos de beleza ou maquiagem", aliquotaIPI: "22%", aliquotaNacional: "15%" },
  { codigo: "8703.23.10", descricao: "Automóveis com motor a explosão, de cilindrada entre 1500 e 3000", aliquotaIPI: "25%", aliquotaNacional: "18%" },
  { codigo: "3004.90.69", descricao: "Outros medicamentos para uso humano", aliquotaIPI: "0%", aliquotaNacional: "12%" },
  { codigo: "8471.41.10", descricao: "Microcomputadores portáteis (notebooks)", aliquotaIPI: "0%", aliquotaNacional: "0%" },
];

export const CEST_DATA: CestRecord[] = [
  { codigo: "01.001.00", descricao: "Cervejas", ncm: "2203.00.00" },
  { codigo: "01.002.00", descricao: "Águas minerais", ncm: "2201.10.00" },
  { codigo: "10.001.00", descricao: "Cosméticos e perfumaria", ncm: "3304.99.90" },
  { codigo: "10.002.00", descricao: "Produtos de barbear", ncm: "3307.10.00" },
  { codigo: "20.001.00", descricao: "Autopeças para veículos", ncm: "8708.99.90" },
  { codigo: "20.002.00", descricao: "Pneus de borracha", ncm: "4011.10.00" },
  { codigo: "28.001.00", descricao: "Medicamentos", ncm: "3004.90.69" },
  { codigo: "28.002.00", descricao: "Luvas cirúrgicas", ncm: "4015.11.00" },
];

export const IBPT_DATA: IbptRecord[] = [
  { ncm: "8471.30.19", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
  { ncm: "8517.12.31", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
  { ncm: "8528.72.00", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
  { ncm: "9403.60.00", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
  { ncm: "6109.10.00", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
  { ncm: "2203.00.00", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
  { ncm: "3304.99.90", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
  { ncm: "3004.90.69", aliquotaFederal: "15,05%", aliquotaEstadual: "18,00%", aliquotaMunicipal: "0,00%" },
];
