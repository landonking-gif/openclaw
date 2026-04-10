import "./utils-ozuUQtXc.js";
import "./links-v2wQeP8P.js";
import "./zod-schema.providers-whatsapp-DvzWkgU9.js";
import "./channel-plugin-common-D4Y28cqs.js";
import "./outbound-media-C4Vs3Wfg.js";
import "./web-media-CkaAIY0r.js";
import "./whatsapp-targets-DyNhcV4L.js";
import "./whatsapp-C64scWUM.js";
import "./whatsapp-surface-CxSSnl7m.js";
import "./whatsapp-shared-B-MU6Ay2.js";
import "./whatsapp-heartbeat-R4ix6swy.js";
import "./common-DbyForkU.js";
import { S as resolveWaWebAuthDir } from "./runtime-whatsapp-boundary-BY3Isjgt.js";
import "./tokens-DeETngSc.js";
import "./heartbeat-Dl8VDfn2.js";
//#region src/channel-web.ts
var LazyWhatsAppAuthDir = class {
	#value = null;
	#read() {
		this.#value ??= resolveWaWebAuthDir();
		return this.#value;
	}
	toString() {
		return this.#read();
	}
	valueOf() {
		return this.#read();
	}
	[Symbol.toPrimitive]() {
		return this.#read();
	}
};
new LazyWhatsAppAuthDir();
//#endregion
export {};
