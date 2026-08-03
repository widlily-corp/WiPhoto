importScripts('grid-worker-logic.js');

self.onmessage = function(e) {
  const { type, data, id } = e.data;
  let result;
  
  try {
    switch (type) {
      case 'calcLayout':
        result = self.GridLogic.calcLayout(data);
        self.postMessage({ type: 'layoutResult', data: result, id });
        break;
      case 'calcVisible':
        result = self.GridLogic.calcVisible(data);
        self.postMessage({ type: 'visibleResult', data: result, id });
        break;
      case 'sort':
        result = self.GridLogic.sortItems(data);
        self.postMessage({ type: 'sortResult', data: { items: result }, id });
        break;
      default:
        console.error('Unknown worker message type:', type);
    }
  } catch (error) {
    self.postMessage({ type: 'error', error: error.message, id });
  }
};
