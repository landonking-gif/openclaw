import "./utils-ozuUQtXc.js";
import "./links-v2wQeP8P.js";
import "./zod-schema.providers-whatsapp-DdRi_Okc.js";
import "./channel-plugin-common-CuBVXJMU.js";
import "./outbound-media-DEmL-jK-.js";
import "./web-media-Bhty-vWo.js";
import "./whatsapp-targets-JnKSMrir.js";
import "./whatsapp-DPIj2SzT.js";
import "./whatsapp-surface-np83T8K1.js";
import "./whatsapp-shared-CA22Mdrl.js";
import "./whatsapp-heartbeat-CwEwANmE.js";
import "./common-DotKVabV.js";
import { S as resolveWaWebAuthDir } from "./runtime-whatsapp-boundary-CwIhJjvT.js";
import "./tokens-CKy9ywkv.js";
import "./heartbeat-BsW5WKin.js";
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
