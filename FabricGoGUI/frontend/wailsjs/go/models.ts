export namespace main {
	
	export class HistoryEntry {
	    pattern: string;
	    model: string;
	    input: string;
	    output: string;
	    time: number;
	
	    static createFrom(source: any = {}) {
	        return new HistoryEntry(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.pattern = source["pattern"];
	        this.model = source["model"];
	        this.input = source["input"];
	        this.output = source["output"];
	        this.time = source["time"];
	    }
	}
	export class ModelsResponse {
	    models: string[];
	    vendors: Record<string, Array<string>>;
	
	    static createFrom(source: any = {}) {
	        return new ModelsResponse(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.models = source["models"];
	        this.vendors = source["vendors"];
	    }
	}
	export class Preferences {
	    baseUrl: string;
	    theme: string;
	    autoStartServer: boolean;
	    lastPattern: string;
	    lastModel: string;
	    lastVendor: string;
	
	    static createFrom(source: any = {}) {
	        return new Preferences(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.baseUrl = source["baseUrl"];
	        this.theme = source["theme"];
	        this.autoStartServer = source["autoStartServer"];
	        this.lastPattern = source["lastPattern"];
	        this.lastModel = source["lastModel"];
	        this.lastVendor = source["lastVendor"];
	    }
	}

}

