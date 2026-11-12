import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';        // ← imported global css
import App from './App';      // ← imported main component

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />    {/*app starts here */}
  </React.StrictMode>
);