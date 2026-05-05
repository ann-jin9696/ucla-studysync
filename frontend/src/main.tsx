import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import '@fontsource/comfortaa/latin-400.css';
import '@fontsource/comfortaa/latin-600.css';
import '@fontsource/poppins/latin-400.css';
import '@fontsource/poppins/latin-500.css';
import '@fontsource/poppins/latin-600.css';
import '@fontsource/quicksand/latin-400.css';
import '@fontsource/quicksand/latin-600.css';
import '@fontsource/quicksand/latin-700.css';
import 'antd/dist/reset.css';
import './styles/global.css';
import { App } from './App';
import { AuthProvider } from './components/AuthProvider';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#79cfb7',
          colorSuccess: '#79cfb7',
          colorWarning: '#f7d970',
          colorText: '#27423b',
          colorTextSecondary: '#6c7f76',
          colorBgBase: '#fffaf0',
          borderRadius: 18,
          fontFamily: '"Poppins", "Avenir Next", "Segoe UI", sans-serif',
        },
        components: {
          Button: {
            borderRadius: 18,
            controlHeight: 44,
            fontWeight: 700,
          },
          Input: {
            borderRadius: 16,
            controlHeight: 44,
          },
          Card: {
            borderRadiusLG: 28,
          },
        },
      }}
    >
      <AuthProvider>
        <App />
      </AuthProvider>
    </ConfigProvider>
  </React.StrictMode>,
);
