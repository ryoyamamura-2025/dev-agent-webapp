# Dev Agent WebApp
Google Agent Development Kit (ADK) を組み込んだ WebApp を開発する

## 参考文献
- [【超速報】Agent Development Kit で会話型エージェントを作成する](https://zenn.dev/google_cloud_jp/articles/1b1cbd5318bdfe)
- [Agent EngineをREST APIとして使えるようにしてみた！](https://sight-r.sts-inc.co.jp/google_cloud_article/agent-engine-api/)

## 参考メモ
出力物の構造
```
Event(content=Content(
  parts=[
    Part(
      text="""それでは、会議のテーマについてお伺いしてもよろしいでしょうか？会議のテーマが決まりましたら、アイデア出しをファシリテートさせていただきます。"""
    ),
  ],
  role='model'
), ...)

Event(content=Content(
  parts=[
    Part(
      text="""会議のテーマ「半日の神戸旅行」について承知いたしました。それでは、さっそくアイデア出しを始めましょう！まず、IdeaAgentさんに「半日の神戸旅行」というテーマで、どのようなアイデアがあるか聞いてみたいと思います。限られた時間で神戸の魅力を楽しむための、創造的なアイデアをお願いします。""",
      thought_signature=xxxx
    ),
    Part(
      function_call=FunctionCall(
        args={
          'request': '半日の神戸旅行で楽しめる創造的なアイデアを提案してください。限られた時間で神戸の魅力を最大限に味わえるようなものをお願いします。'
        },
        id='adk-xxxxx',
        name='IdeaAgent'
      )
    ),
  ],
  role='model'
), ...)

Event(content=Content(
  parts=[
    Part(
      function_response=FunctionResponse(
        id='adk-xxxxx',
        name='IdeaAgent',
        response={
          'result': """はい、承知いたしました。半日の神戸旅行で誰もがあっと驚き、限られた時間で神戸の魅力を最大限に味わえる、創造的なアイデアを提案します。..."""
        }
      )
    ),
  ],
  role='user'
), ...)


Event(content=Content(
  parts=[
    Part(
      text="""IdeaAgentさんから、非常に創造的なアイデアが出されましたね！""",
      thought_signature=xxxx'
    ),
  ],
  role='model'
), ...)
```