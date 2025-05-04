// utils.js
export function extractJsonAndText(response) {
    const jsonMatch = response.match(/```json([\s\S]*?)```/);
    if (!jsonMatch) {
      return {
        beforeText: response.trim(), // If no JSON, treat all as beforeText
        afterText: "",
        data: null
      };
    }
  
    const beforeText = response.slice(0, jsonMatch.index).trim();
    const jsonString = jsonMatch[1].trim();
    const afterText = response.slice(jsonMatch.index + jsonMatch[0].length).trim();
  
    let parsedJson = null;
    try {
      parsedJson = JSON.parse(jsonString);
    } catch (e) {
      console.error("Failed to parse JSON:", e);
    }
  
    return {
      beforeText,
      afterText,
      data: parsedJson
    };
  }
  