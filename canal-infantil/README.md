# Turminha do Pingo: canal infantil educativo

Um canal em português para crianças de 2 a 5 anos. O apresentador é o **Pingo**, uma gotinha d'água azul.
Os vídeos são curtos, coloridos e repetitivos de propósito (a criança aprende repetindo), e todos terminam com um quiz.

Este repositório gera os vídeos **automaticamente**:

```bash
./setup.sh                                          # baixa a voz pt-BR e a fonte (1x)
python3 gerar.py episodios/cores.json               # vídeo 16:9 + thumbnail + título/descrição/capítulos
python3 gerar.py episodios/cores.json --short       # Short vertical 9:16
```

Saída em `saida/`: `.mp4`, `-thumb.jpg` e `-youtube.txt`, que traz o texto pronto para colar no upload.

Tudo é original e livre de direitos autorais:
- O personagem e os objetos são desenhados por código.
- A música também é gerada por código.
- A fonte é a Fredoka (licença OFL).
- A voz é o Piper TTS com a voz "edresson" (CC BY 4.0, por isso o crédito vai na descrição).

---

## 1. O que só você pode fazer (cerca de 30 min)

1. Crie o canal com uma conta Google sua e ative a verificação em duas etapas. Use o nome **Turminha do Pingo**, mas antes procure no YouTube se o nome já existe.
2. Em *Configurações → Canal → Configurações avançadas*, marque **"Sim, é conteúdo para crianças"** para o canal inteiro.
3. Use como foto de perfil um recorte do Pingo (dá para tirar da thumbnail) e faça o banner em 2560×1440.
4. Faça o upload do vídeo e do Short, colando o texto do `-youtube.txt`. Programe a publicação para as 9h ou as 17h, que são os horários em que pais colocam vídeo para os filhos.

## 2. Monetização: o que esperar de verdade

| Requisito do YouTube Partner Program | Situação |
|---|---|
| 1.000 inscritos | e também uma destas: |
| 4.000 horas assistidas em 12 meses (vídeos longos) **ou** 10 milhões de views de Shorts em 90 dias | |

Canal **"feito para crianças"** tem estas consequências (são regras da lei COPPA, não dá para escapar):
- Os anúncios não são personalizados, então o RPM é **bem mais baixo** do que em canais adultos. Em canal infantil em português, conte com algo na faixa de **centavos a poucos reais por 1.000 views**.
- Não tem comentários, sininho de notificação, membros, Super Thanks, cards nem telas finais.
- Por isso o dinheiro vem de **volume** e de vídeos **longos**: compilações de 10 a 30 minutos que os pais deixam rodando.

**Risco nº 1: a política de "conteúdo inautêntico / produzido em massa" (2025).**
O YouTube recusa ou desmonetiza canais que parecem fábrica de vídeos iguais. Por isso:
- Não publique 50 vídeos idênticos trocando só a palavra. Cada episódio precisa ter algo novo: tema, objetos, uma musiquinha ou uma pequena história.
- Revise cada vídeo antes de subir. **Ouça a voz**: o sintetizador às vezes come o "ã" (por exemplo, "maçã").
- Com o tempo, considere gravar a voz do Pingo você mesmo (ou com alguém da família). Isso aumenta muito a retenção e a "autenticidade". O motor já sincroniza a boca do Pingo com qualquer áudio.

**Fontes de receita além do AdSense** (comece já, sem esperar os 1.000 inscritos):
- Livro de colorir do Pingo na Amazon KDP, reaproveitando os desenhos que o código já gera.
- Músicas no Spotify e em outras plataformas, distribuídas via DistroKid ou ONErpm.
- Licenciar os vídeos para apps e escolas.

## 3. Plano de conteúdo (primeiros 90 dias)

- **Ritmo:** 2 vídeos longos por semana e 1 Short por dia (cada vídeo longo rende de 3 a 5 Shorts).
- **A partir do mês 2:** uma compilação de 20 a 30 minutos por semana, juntando episódios. É ela que gera horas de exibição.

Próximos episódios (cada um é só um novo `.json` e, quando for o caso, novos desenhos em `object_sprite`):

1. Números de 1 a 10 (contando maçãs)
2. Formas: círculo, quadrado, triângulo, estrela
3. Animais da fazenda e seus sons
4. Frutas
5. Vogais A E I O U
6. Alfabeto (em 3 partes)
7. Grande e pequeno
8. Dia e noite
9. Partes do corpo
10. Meios de transporte
11. Cores do arco-íris (revisão)
12. Contando até 20
13. Animais da selva
14. Emoções: feliz, triste, bravo
15. Escovar os dentes
16. Hora de dormir
17. Em cima e embaixo
18. Legumes
19. Clima: sol, chuva, vento (o Pingo vira chuva!)
20. Dias da semana

## 4. Próximas melhorias no motor

- Narração com voz humana: passar um `.wav` por fala em vez de TTS.
- Modo compilação: juntar N episódios num vídeo de 20 minutos ou mais.
- Musiquinha cantada do tema do episódio.
- Upload automático pela YouTube Data API. Isso exige credenciais OAuth suas, que eu não tenho.
