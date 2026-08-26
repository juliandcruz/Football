# ValueBet Football V3 — Mobile Web App

Aplicación web mobile-first para visualizar oportunidades de value betting.

## Ejecutar
```bash
pip install -r requirements.txt
streamlit run app.py
```

Después abre la URL que indique Streamlit desde el móvil o el ordenador.

## Publicarla en internet
La opción sencilla es Streamlit Community Cloud: conecta un repositorio GitHub y despliega `app.py`. La documentación oficial de Streamlit incluye el flujo de despliegue y soporte para apps multipágina.

## Arquitectura prevista
1. `data/` — datos históricos y oportunidades.
2. V2 — modelos y backtesting.
3. V3 — interfaz móvil.
4. Próxima fase — API de cuotas, datos de jugadores y actualización automática.

## Seguridad
No pongas claves API directamente en el código. Usa variables de entorno / secrets del proveedor.

## Importante
Los números de la demo son ficticios y solo sirven para comprobar la interfaz.
