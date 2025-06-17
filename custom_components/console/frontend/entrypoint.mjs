import { ClipboardAddon } from './@xterm/addon-clipboard.mjs';
import { FitAddon } from './@xterm/addon-fit.mjs';
import { WebLinksAddon } from './@xterm/addon-web-links.mjs';
import { Terminal } from './@xterm/xterm.mjs';

const throttle = (func, interval = 1) => {
	let timeout;
	let lastRun = 0;

	function runner(...args) {
		lastRun = Date.now();
		return func.apply(this, args);
	};

	return function(...args) {
		clearTimeout(timeout);
		const waitTime = interval + lastRun - Date.now();
		if (waitTime <= 0) {
			return runner.apply(this, args);
		}
		timeout = setTimeout(runner, waitTime);
	};
};

class Scope {
	#disposables = [];

	bind(...disposables) {
		this.onDispose(...disposables.map(d => d.dispose.bind(d)));
	}

	onDispose(...fns) {
		this.#disposables.push(...fns);
	}

	dispose() {
		let dispose;
		while (dispose = this.#disposables.pop()) {
			dispose();
		}
	}
}

class State {
	#state = {};
	#targets = [];

	get(key) {
		return this.#state[key];
	}

	set(key, value) {
		this.#state[key] = value;
		for (const target of this.#targets) {
			target[key] = value;
		}
		return value;
	}

	bindProps(target, props) {
		for (const prop of props) {
			Object.defineProperty(target, prop, {
				get: () => this.get(prop),
				set: value => this.set(prop, value),
			});
		}
	}

	addSyncTargets(...targets) {
		this.#targets.push(...targets);
		for (const target of this.#targets) {
			Object.assign(target, this.#state);
		}
	}
}

class AutoFitAddon extends FitAddon {
	#scope = new Scope();
	#resizeObserver = new ResizeObserver(throttle(() => this.fit()));

	activate(terminal) {
		if (!terminal.element) {
			this.#scope.bind(
				terminal._core.onWillOpen(() => this.activate(terminal)),
			);
			return;
		}

		super.activate(terminal);

		this.#resizeObserver.observe(terminal.element.parentElement);
		this.#scope.onDispose(() => {
			this.#resizeObserver.disconnect();
		});
		this.fit();
	}

	dispose() {
		this.#scope.dispose();
		super.dispose();
	}
}

class HassAddon {
	#terminal;
	#connection;
	#scope = new Scope();
	#sessionId = crypto.randomUUID();

	#message(msg) {
		return { ...msg, session_id: this.#sessionId };
	}

	async #sendMessagePromise(msg) {
		return await this.#connection?.sendMessagePromise(
			this.#message(msg)
		);
	}

	async #subscribeMessage() {
		const unsubscribe = await this.#connection.subscribeMessage(
			data => this.#terminal.write(data),
			this.#message({ type: 'console/create_session' }),
		);
		this.#scope.onDispose(unsubscribe);
	}

	#send(data) {
		return this.#sendMessagePromise({ type: 'console/input', data });
	}

	#resize({ cols, rows }) {
		return this.#sendMessagePromise({ type: 'console/resize', cols, rows });
	}

	connect(connection) {
		if (this.#connection == connection) {
			return;
		}

		if (!this.#terminal) {
			throw new Error('Cannot connect without a terminal');
		}

		this.#connection = connection;
		this.#subscribeMessage();
	}

	activate(terminal) {
		this.#terminal = terminal;

		this.#scope.bind(
			terminal.onBinary(this.#send.bind(this)),
			terminal.onData(this.#send.bind(this)),
			terminal.onResize(this.#resize.bind(this)),
		);

		this.#resize(terminal);
	}

	dispose() {
		this.#scope.dispose();
	}
}

const DEFAULT_ADDONS = {
	hass: HassAddon,
	weblinks: WebLinksAddon,
	clipboard: ClipboardAddon,
	autofit: AutoFitAddon,
};

class TerminalElement extends HTMLElement {
	#hass;
	#root;
	#terminal;
	#addons;

	constructor() {
		super();

		const shadow = this.attachShadow({ mode: 'open' });
		shadow.innerHTML = `
			<link rel="stylesheet" href="${URL.parse('./@xterm/xterm.min.css', import.meta.url)}">
			<style>
				.viewport {
					height: 100%;
					background: black;
				}
				.viewport .terminal {
					padding: 16px;
				}
			</style>
			<div class="viewport"></div>
		`;

		this.#root = shadow.querySelector('.viewport');
	}

	get hass() {
		return this.#hass;
	}

	set hass(hass) {
		this.#hass = hass;
		this.#addons.hass?.connect(hass.connection);
	}

	connectedCallback() {
		const terminal = this.#terminal = new Terminal();

		this.#addons = {};
		for (const [key, Factory] of Object.entries(DEFAULT_ADDONS)) {
			const addon = this.#addons[key] = new Factory();
			terminal.loadAddon(addon);
		}

		if (this.#hass?.connection) {
			this.#addons.hass.connect(this.#hass.connection);
		}

		terminal.open(this.#root);
	}

	disconnectedCallback() {
		this.#addons = undefined;
		this.#terminal.dispose();
	}
}
customElements.define("terminal-element", TerminalElement);

// Loads in ha-config-dashboard which is used to copy styling
async function loadConfigDashboard() {
	await customElements.whenDefined("partial-panel-resolver");
	const ppr = document.createElement("partial-panel-resolver");
	ppr.hass = {
		panels: [{
			url_path: "tmp",
			component_name: "iframe",
		}]
	};
	ppr._updateRoutes();
	await ppr.routerOptions.routes.tmp.load();
	await customElements.whenDefined('hass-subpage');
};

class TerminalPanel extends HTMLElement {
	#state = new State();
	#shadow = this.attachShadow({ mode: 'open' });

	constructor() {
		super();
		this.#state.bindProps(this, ['hass', 'narrow']);
	}

	async connectedCallback() {
		await loadConfigDashboard();

		this.#shadow.innerHTML = `
			<hass-subpage header="Console" main-page>
				<terminal-element></terminal-element>
			</hass-subpage>
		`;

		this.#state.addSyncTargets(
			...this.#shadow.querySelectorAll(
				'hass-subpage, terminal-element'
			),
		);
	}
}
customElements.define("terminal-panel", TerminalPanel);
