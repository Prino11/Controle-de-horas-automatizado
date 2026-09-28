& "C:\Program Files\Git\cmd\git.exe" remote add origin https://github.com/Prino11/Controle-de-horas-automatizado.git
& "C:\Program Files\Git\cmd\git.exe" fetch origin
& "C:\Program Files\Git\cmd\git.exe" reset --mixed origin/main
& "C:\Program Files\Git\cmd\git.exe" add .
& "C:\Program Files\Git\cmd\git.exe" commit -m "feat: integracao com IA e testes"
& "C:\Program Files\Git\cmd\git.exe" branch -M main
& "C:\Program Files\Git\cmd\git.exe" push -u origin main -f
