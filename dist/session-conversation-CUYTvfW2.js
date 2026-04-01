import { n as parseTelegramTopicConversation } from "./conversation-id-DJQ6o9tk.js";
import "./telegram-core-Chg4nuCi.js";
//#region extensions/telegram/src/session-conversation.ts
function resolveTelegramSessionConversation(params) {
	const parsed = parseTelegramTopicConversation({ conversationId: params.rawId });
	if (!parsed) return null;
	return {
		id: parsed.chatId,
		threadId: parsed.topicId,
		baseConversationId: parsed.chatId,
		parentConversationCandidates: [parsed.chatId]
	};
}
//#endregion
export { resolveTelegramSessionConversation as t };
