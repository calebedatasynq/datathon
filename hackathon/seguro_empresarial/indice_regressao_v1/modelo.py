"""Regressão logística ordinal penalizada; score não é probabilidade de compra."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

PLANOS=np.array(['ESSENCIAL','PRATICO','TOTAL'])
EMP='funcionarios_estimados_empresa'; EST='estoque_medio_estimado'; BEM='valor_bens_ponderado_estabelecimento'
CAT=['grupo_atividade','tipo_unidade']
SPECS={'patrimonio_emprego':[EMP,EST,BEM],
       'com_faturamento':[EMP,EST,BEM,'faturamento_mensal_empresa'],
       'com_contexto':[EMP,EST,BEM,'grupo_atividade','tipo_unidade','quantidade_estabelecimentos_empresa'],
       'com_area_loja':[EMP,EST,BEM,'area_m2','possui_termo_loja','possui_termo_galeria']}
CENARIOS={'central':(.60,.75), 'mais_abrangente':(.50,.65), 'mais_restritivo':(.70,.85)}

def criterios(df,cenario='central'):
    qpat,qemp=CENARIOS[cenario]
    return {'cenario':cenario,'quantil_patrimonio':qpat,'quantil_empregados':qemp,
            'estoque':float(df[EST].quantile(qpat)), 'bens':float(df[BEM].quantile(qpat)),
            'empregados':float(df.drop_duplicates('empresa_id')[EMP].quantile(qemp))}

def rotular(df,c):
    # Política do protótipo: prioridades relativas, não elegibilidade nem necessidade confirmada.
    y=np.zeros(len(df),dtype=int)
    y[(df[EST].to_numpy()>=c['estoque']) | (df[BEM].to_numpy()>=c['bens'])]=1
    y[df[EMP].to_numpy()>=c['empregados']]=2
    return y

def objetivo(theta,x,y,alpha):
    beta=theta[:-2];t1=theta[-2];t2=t1+np.logaddexp(0,theta[-1])+1e-4
    z=x@beta; f1=expit(t1-z);f2=expit(t2-z)
    p=np.maximum(np.column_stack([f1,f2-f1,1-f2]),1e-14)
    n=len(y);g1=np.zeros(n);g2=np.zeros(n)
    m0=y==0;m1=y==1;m2=y==2
    g1[m0]=-(1-f1[m0]);g1[m1]=f1[m1]*(1-f1[m1])/p[m1,1]
    g2[m1]=-f2[m1]*(1-f2[m1])/p[m1,1];g2[m2]=f2[m2]
    gz=-g1-g2
    loss=-np.log(p[np.arange(n),y]).mean()+alpha*np.dot(beta,beta)/(2*n)
    grad=np.r_[x.T@gz+alpha*beta,(g1+g2).sum(),g2.sum()*expit(theta[-1])]/n
    return loss,grad

class Ordinal:
    def __init__(self,colunas,alpha=1.):self.colunas=colunas;self.alpha=alpha
    def fit(self,df,y):
        cats=[c for c in self.colunas if c in CAT];nums=[c for c in self.colunas if c not in CAT]
        num=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),FunctionTransformer(np.log1p,feature_names_out='one-to-one'),StandardScaler())
        cat=OneHotEncoder(drop='first',handle_unknown='ignore',sparse_output=False)
        self.prep=ColumnTransformer([('num',num,nums),('cat',cat,cats)])
        xx=self.prep.fit_transform(df[self.colunas]);self.mask=xx.std(axis=0)>1e-10;x=xx[:,self.mask]
        self.names=self.prep.get_feature_names_out()[self.mask].tolist()
        self.opt=minimize(objetivo,np.r_[np.zeros(x.shape[1]),-1.,1.],args=(x,y,self.alpha),jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-11,'gtol':1e-6})
        if not self.opt.success:raise RuntimeError(str(self.opt.message))
        self.beta=self.opt.x[:-2]; self.thresholds=np.array([self.opt.x[-2],self.opt.x[-2]+np.logaddexp(0,self.opt.x[-1])+1e-4])
        return self
    def design(self,df):return self.prep.transform(df[self.colunas])[:,self.mask]
    def predict(self,df):
        x=self.design(df);z=x@self.beta;c=expit(self.thresholds);score=expit(z)
        f=expit(self.thresholds[None,:]-z[:,None]);p=np.column_stack([f[:,0],f[:,1]-f[:,0],1-f[:,1]])
        return p,np.searchsorted(self.thresholds,z,side='right'),score,c,x*self.beta
