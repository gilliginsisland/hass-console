import { ClipboardAddon } from './@xterm/addon-clipboard.mjs';
import { FitAddon } from './@xterm/addon-fit.mjs';
import { WebLinksAddon } from './@xterm/addon-web-links.mjs';
import { Terminal } from './@xterm/xterm.mjs';

class Scope {
	#disposables = [];

	addEventListener(target, type, cb) {
		const dispose = () => {
			target.removeEventListener(type, cb);
		};
		target.addEventListener(type, cb);
		this.#disposables.push({ dispose });
	}

	addDisposable(...disposables) {
		this.#disposables.push(...disposables);
	}

	dispose() {
		let d;
		while (d = this.#disposables.pop()) {
			d.dispose();
		}
	}
}

class TerminalElement extends HTMLElement {
	#hass;
	#root;
	#scope = new Scope();
	#terminal = new Terminal();
	#addons = {
		weblinks: new WebLinksAddon(),
		clipboard: new ClipboardAddon(),
		fit: new FitAddon(),
		hass: new HassAddon(),
	};
	#shadow = this.attachShadow({ mode: 'open' });

	constructor() {
		super();
		this.#scope.addDisposable(this.#terminal);

		this.#shadow.innerHTML = `
			<link rel="stylesheet" href="${URL.parse('./@xterm/xterm.min.css', import.meta.url)}">
			<div class="shadow-root" style="width: 100%; height: 100%;"></div>
		`;
		this.#root = this.#shadow.querySelector('.shadow-root');
	}

	get hass() {
		return this.#hass;
	}

	set hass(hass) {
		this.#hass = hass;
		this.#addons.hass.connection = hass.connection;
	}

	connectedCallback() {
		for (const [, addon] of Object.entries(this.#addons)) {
			this.#terminal.loadAddon(addon);
		}
		this.#terminal.open(this.#root);

		this.#scope.addEventListener(window, 'resize', () => this.#addons.fit.fit());
		this.#addons.fit.fit();
	}

	disconnectedCallback() {
		this.#scope.dispose();
	}
}
customElements.define("terminal-element", TerminalElement);

class HassAddon {
	#terminal;
	#connection;
	#scope = new Scope();
	#sessionId = crypto.randomUUID();

	get connection() {
		return this.#connection;
	}

	set connection(connection) {
		this.#connection = connection;
	}

	#message(msg) {
		return { ...msg, session_id: this.#sessionId };
	}

	#sendMessagePromise(msg) {
		return this.#connection.sendMessagePromise(
			this.#message(msg)
		);
	}

	#recv(data) {
		this.#terminal.write(data);
	}

	#send(data) {
		this.#sendMessagePromise({ type: 'console/input', data });
	}

	#resize({ cols, rows }) {
		this.#sendMessagePromise({ type: 'console/resize', cols, rows });
	}

	async activate(terminal) {
		this.#terminal = terminal;

		const dispose = await this.#connection?.subscribeMessage(
			data => this.#recv(data),
			this.#message({ type: 'console/create_session' }),
		);
		this.#scope.addDisposable({ dispose });

		this.#scope.addDisposable(
			terminal.onBinary(this.#send.bind(this)),
			terminal.onData(this.#send.bind(this)),
			terminal.onResize(this.#resize.bind(this)),
		);

		this.#resize({
			cols: this.#terminal.cols,
			rows: this.#terminal.rows,
		});
	}

	dispose() {
		this.#scope.dispose();
	}
}
