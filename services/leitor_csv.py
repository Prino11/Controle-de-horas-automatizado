import pandas as pd
from models.registro_ponto import RegistroPonto

def ler_registros_csv(caminho_csv: str) -> list[RegistroPonto]:
    df = pd.read_csv(caminho_csv)


    registros = []
    for _, row in df.iterrows():
        registro = RegistroPonto(
            funcionario= row["funcionario"],
            data= row["data"],
            entrada= row["entrada"],
            saida= row["saida"]

        )
        registros.append(registro)
    return registros