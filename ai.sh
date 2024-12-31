export INPUT_PROMPT=$1
[[ -z $INPUT_PROMPT ]] && \
	export INPUT_PROMPT="Suggest 1 thing to improve the program."
echo $INPUT_PROMPT
[[ -z $DEBUG ]] && alias curl='echo' || unalias curl
curl -X POST 'https://api.anthropic.com/v1/messages' \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "$(jq -n \
  --arg p1 "$(cat prompt.txt)" \
  --arg p2 "$(cat custom_commands.py)" \
  --arg p3 "$(cat blenderocc.py)" \
  --arg p4 "$(echo $INPUT_PROMPT)" \
    '{
      model: "claude-3-sonnet-20241022",
      max_tokens: 512,
      system: "You are a CAD expert specializing in OpenCascade and Blender integration. Focus on providing practical solutions and code examples.",
      messages: [
        {role: "user", content: [{type: "text", text: $p1}]},
        {role: "assistant", content: [{type: "text", text: "Got it. Next, show me the code."}]},
        {role: "user", content: [{type: "text", text: $p2}]},
        {role: "assistant", content: [{type: "text", text: "Those custom commands are only scratching the surface. Next, show me the main program."}]},
        {role: "user", content: [{type: "text", text: $p3}]},
        {role: "assistant", content: [{type: "text", text: "Excellent. Now that I understand the program, I can make a suggestion."}]},
        {role: "assistant", content: [{type: "text", text: "Here is a short snippet:"}]}
      ]
     }')"|jq '.' > out.json
cat out.json | jq -r '.content[0].text'

