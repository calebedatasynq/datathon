"""Conferências dos dados reais e barreiras contra avaliação sem referência."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from analisar import ler, ampliada, PLANOS
from treinar import validar_rotulos, SemRotulos, ESPECIFICACOES


class Integridade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=pd.read_csv(ROOT/'dados/preparados/base_desenvolvimento.csv')
        cls.comum=pd.read_csv(ROOT/'dados/preparados/base_teste_comum.csv')
        cls.rotulos=pd.read_csv(ROOT/'dados/rotulos/rotulos_revisados.csv')

    def test_01_contagens_desenvolvimento(self):
        self.assertEqual((len(self.base),self.base.empresa_id.nunique()),(2978,2500))

    def test_02_contagens_comum(self):
        self.assertEqual((len(self.comum),self.comum.empresa_id.nunique()),(144,120))

    def test_03_chaves_sem_duplicacao(self):
        for x in [self.base,self.comum]:
            self.assertFalse(x.duplicated(['empresa_id','imovel_id']).any())
            self.assertFalse(x[['empresa_id','imovel_id']].isna().any().any())

    def test_04_faturamento_sem_rateio(self):
        for flag,x in [(False,self.base),(True,self.comum)]:
            e=ler('empresas',flag).set_index('empresa_id')
            np.testing.assert_array_equal(x.faturamento_mensal_empresa,x.empresa_id.map(e.faturamento_mensal))

    def test_05_funcionarios_sem_rateio(self):
        for flag,x in [(False,self.base),(True,self.comum)]:
            e=ler('empresas',flag).set_index('empresa_id')
            np.testing.assert_array_equal(x.funcionarios_estimados_empresa,x.empresa_id.map(e.quantidade_funcionarios_estimada))

    def test_06_quantidade_unidades(self):
        for flag,x in [(False,self.base),(True,self.comum)]:
            a=ler('enderecos_estabelecimentos',flag)
            np.testing.assert_array_equal(x.quantidade_estabelecimentos_empresa,x.empresa_id.map(a.groupby('empresa_id').size()))

    def test_07_estoque_por_estabelecimento(self):
        for flag,x in [(False,self.base),(True,self.comum)]:
            s=ler('sinais_financeiros_operacionais',flag)
            j=x.merge(s,on=['empresa_id','imovel_id'],validate='one_to_one')
            np.testing.assert_array_equal(j.estoque_medio_estimado_x,j.estoque_medio_estimado_y)

    def test_08_soma_bens_por_estabelecimento(self):
        for flag,x in [(False,self.base),(True,self.comum)]:
            b=ler('bens_cadastrados',flag)
            esperado=b.groupby(['empresa_id','imovel_id_referencia']).valor_bem_ponderado_referencia.sum()
            indice=pd.MultiIndex.from_frame(x[['empresa_id','imovel_id']])
            np.testing.assert_array_equal(x.valor_bens_ponderado_estabelecimento,esperado.reindex(indice))
            self.assertEqual(x.valor_bens_ponderado_estabelecimento.sum(),b.valor_bem_ponderado_referencia.sum())

    def test_09_contagem_bens(self):
        for flag,x in [(False,self.base),(True,self.comum)]:
            self.assertEqual(x.quantidade_bens_cadastrados.sum(),len(ler('bens_cadastrados',flag)))

    def test_10_area_indisponivel(self):
        for flag,x,n in [(False,self.base,1838),(True,self.comum,87)]:
            a=ler('enderecos_estabelecimentos',flag)
            j=x.merge(a,on=['empresa_id','imovel_id'],validate='one_to_one')
            m=j.area_cadastrada_m2.eq(0)|j.area_cadastrada_m2.isna()|j.origem_area_y.eq('NAO_DISPONIVEL')
            np.testing.assert_array_equal(j.area_m2.isna(),m)
            self.assertEqual(x.area_m2.isna().sum(),n)
            np.testing.assert_array_equal(j.loc[~m,'area_m2'],j.loc[~m,'area_cadastrada_m2'])

    def test_11_flags_fieis_ao_cadastro(self):
        for flag,x in [(False,self.base),(True,self.comum)]:
            a=ler('enderecos_estabelecimentos',flag)
            j=x.merge(a,on=['empresa_id','imovel_id'])
            for c in ['possui_termo_loja','possui_termo_galeria']:
                np.testing.assert_array_equal(j[c+'_x'],j[c+'_y'].map({'SIM':1,'NAO':0}))

    def test_12_classes_catalogo(self):
        self.assertEqual(set(ler('catalogo_coberturas_fixas_planos').plano),set(PLANOS))

    def test_13_planos_referencia_ausentes(self):
        for x in [self.base,self.comum]:self.assertTrue(x.plano_recomendado.isna().all())

    def test_14_treinamento_sem_rotulos_bloqueado(self):
        with self.assertRaises(SemRotulos):validar_rotulos(self.base,self.rotulos.assign(plano_referencia=pd.NA))

    def test_15_rotulo_invalido_rejeitado(self):
        x=self.rotulos.iloc[:1].copy();x['plano_referencia']='OURO'
        with self.assertRaisesRegex(ValueError,'Plano diferente'):validar_rotulos(self.base,x)

    def test_16_rotulo_sem_procedencia_rejeitado(self):
        x=self.rotulos.iloc[:1].copy();x['plano_referencia']='ESSENCIAL';x['revisor']=''
        with self.assertRaisesRegex(ValueError,'procedência'):validar_rotulos(self.base,x)

    def test_17_rotulo_duplicado_rejeitado(self):
        x=pd.concat([self.rotulos.iloc[:1],self.rotulos.iloc[:1]])
        with self.assertRaisesRegex(ValueError,'duplicada'):validar_rotulos(self.base,x)

    def test_18_rotulo_imovel_inexistente_rejeitado(self):
        x=self.rotulos.iloc[:1].copy();x['imovel_id']='FORA_DA_BASE'
        with self.assertRaisesRegex(ValueError,'fora da base'):validar_rotulos(self.base,x)

    def test_19_grupos_treino_avaliacao(self):
        p=pd.read_csv(ROOT/'resultados/particao_empresas_proposta.csv')
        a=set(p[p.particao_proposta.eq('treino_desenvolvimento')].empresa_id)
        b=set(p[p.particao_proposta.eq('avaliacao_reservada')].empresa_id)
        self.assertFalse(a&b)
        self.assertEqual(len(p),len(self.base))

    def test_20_casos_cobrem_todas_atividades(self):
        x=pd.read_csv(ROOT/'resultados/casos_demonstracao.csv')
        self.assertEqual(set(x.grupo_atividade),set(self.base.grupo_atividade))
        self.assertEqual(x[x.caso.str.startswith('atividade_')].caso.nunique(),10)

    def test_21_casos_valores_conferidos(self):
        casos=pd.read_csv(ROOT/'resultados/casos_demonstracao.csv')
        j=casos.merge(self.base,on=['empresa_id','imovel_id'],validate='many_to_one',suffixes=('_caso','_base'))
        for c in ['faturamento_mensal_empresa','funcionarios_estimados_empresa','area_m2','estoque_medio_estimado','valor_bens_ponderado_estabelecimento']:
            np.testing.assert_allclose(j[c+'_caso'],j[c+'_base'],equal_nan=True,rtol=0,atol=0)
        self.assertEqual(len(j),23)

    def test_22_maturidade_duplicada(self):
        e=ler('empresas')
        np.testing.assert_array_equal(e.dependencia_digital_pct,e.indice_maturidade_digital)

    def test_23_estoques_nao_sao_identicos(self):
        s=ler('sinais_financeiros_operacionais')
        self.assertFalse(s.estoque_medio_estimado.equals(s.estoque_pico_estimado))
        self.assertTrue(s.estoque_pico_estimado.ge(s.estoque_medio_estimado).all())

    def test_24_sem_id_ou_alvo_nos_preditores(self):
        for cols in ESPECIFICACOES.values():
            self.assertFalse(set(cols)&{'empresa_id','imovel_id','plano_recomendado','plano_referencia','elegivel'})
            self.assertTrue(set(cols).issubset(self.base.columns))

    def test_25_hashes_fontes(self):
        manifest=json.loads((ROOT/'dados/preparados/relatorio_preparacao.json').read_text())
        for resumo in manifest['bases'].values():
            for f in resumo['fontes'].values():
                self.assertEqual(hashlib.sha256(Path(f['arquivo']).read_bytes()).hexdigest(),f['sha256'])

    def test_26_sem_resultado_preditivo_inventado(self):
        x=json.loads((ROOT/'resultados/estado_modelagem.json').read_text())
        if self.rotulos.plano_referencia.notna().sum()==0:
            self.assertFalse(x['treinado']);self.assertIsNone(x['acuracia']);self.assertIsNone(x['limites_score'])
        else:
            self.assertTrue(x['treinado']);self.assertIn('metricas_avaliacao',x)


class Registro(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.registros=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.registros.append({'teste':test.id().split('.')[-1],'resultado':'APROVADO','detalhe':test.shortDescription() or ''})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.registros.append({'teste':test.id().split('.')[-1],'resultado':'FALHOU','detalhe':str(err[1])})
    def addError(self,test,err):
        super().addError(test,err);self.registros.append({'teste':test.id().split('.')[-1],'resultado':'ERRO','detalhe':str(err[1])})


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Integridade)
    with (ROOT/'resultados/testes_execucao.txt').open('w') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Registro).run(suite)
    pd.DataFrame(result.registros).to_csv(ROOT/'resultados/testes_integridade.csv',index=False,encoding='utf-8-sig')
    print(f'Testes: {result.testsRun}; falhas: {len(result.failures)}; erros: {len(result.errors)}')
    if not result.wasSuccessful():sys.exit(1)
