import requests
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import re
from fuzzywuzzy import fuzz
import unicodedata

# =============================================================================
# FUNCIONES DE PROCESAMIENTO
# =============================================================================

def normalizar_texto(texto):
    """
    Convierte el texto a minúsculas, remueve diacríticos,
    realiza reemplazos específicos y elimina caracteres no deseados.
    """
    texto = str(texto).lower()
    # Remover diacríticos (ej.: "cáscara" -> "cascara")
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn')
    # Reemplazos específicos (según el dominio)
    texto = texto.replace("9 1/2", "9.5").replace("9 1/2'", "9.5").replace("9.5'", "9.5")
    texto = texto.replace("20'", "20in")
    # Se conservan números, letras, puntos, comas y espacios
    texto = re.sub(r'[^a-z0-9., ]', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def mejor_fuzzy_score(a, b):
    """
    Devuelve el máximo entre distintos métodos de fuzzy matching.
    """
    return max(
        fuzz.ratio(a, b),
        fuzz.partial_ratio(a, b),
        fuzz.token_sort_ratio(a, b),
        fuzz.token_set_ratio(a, b)
    )

def exportar_a_excel(partidas_detectadas):
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", 
                                             filetypes=[("Excel files", "*.xlsx")])
    if not file_path:
        return
    df = pd.DataFrame.from_dict(partidas_detectadas, orient='index')
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'Partida'}, inplace=True)
    df["Total"] = df["cantidad"] * df["precio_unitario"]
    df.to_excel(file_path, index=False)
    messagebox.showinfo("Exportación Completa", "Los resultados han sido exportados correctamente.")

def mostrar_resultados(partidas_detectadas):
    ventana_resultados = tk.Toplevel(bg="#f9f9f9")
    ventana_resultados.title("Resultados de Validación")
    ventana_resultados.geometry("900x600")
    ventana_resultados.minsize(600, 400)

    ventana_resultados.columnconfigure(0, weight=1)
    ventana_resultados.rowconfigure(0, weight=1)

    frame_principal = tk.Frame(ventana_resultados, bg="#f9f9f9")
    frame_principal.grid(row=0, column=0, sticky="nsew")
    frame_principal.columnconfigure(0, weight=1)
    frame_principal.rowconfigure(0, weight=1)

    canvas = tk.Canvas(frame_principal, bg="#f9f9f9", highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="nsew")

    scrollbar_vertical = ttk.Scrollbar(frame_principal, orient="vertical", command=canvas.yview)
    scrollbar_vertical.grid(row=0, column=1, sticky="ns")

    scrollbar_horizontal = ttk.Scrollbar(frame_principal, orient="horizontal", command=canvas.xview)
    scrollbar_horizontal.grid(row=1, column=0, sticky="ew")

    canvas.configure(yscrollcommand=scrollbar_vertical.set, xscrollcommand=scrollbar_horizontal.set)

    frame_interno = tk.Frame(canvas, bg="#f9f9f9")
    canvas.create_window((0, 0), window=frame_interno, anchor="nw")

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    frame_interno.bind("<Configure>", on_frame_configure)

    estilo = ttk.Style()
    estilo.theme_use("clam")
    estilo.configure("Treeview", font=("Segoe UI", 10), rowheight=26,
                     background="white", fieldbackground="white")
    estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                     background="#4a90e2", foreground="white")
    estilo.map("Treeview",
               background=[("selected", "#cce5ff")],
               foreground=[("selected", "#000000")],
               font=[("selected", ("Segoe UI", 10, "bold"))])

    columnas = ("Partida", "Descripción", "Unidad de Medida",
                "Precio Unitario", "Cantidad", "Total",
                "Similitud", "Palabra Coincidente", "Comentario")
    tree = ttk.Treeview(frame_interno, columns=columnas, show='headings')
    for col in columnas:
        tree.heading(col, text=col)
        if col == "Comentario":
            tree.column(col, anchor="center", width=350)
        else:
            tree.column(col, anchor="center", width=110)

    tree.pack(expand=True, fill="both")

    tree.tag_configure("verde", background="#e3f9e5")
    tree.tag_configure("naranja", background="#fff4e5")
    tree.tag_configure("amarillo", background="#fffce5")

    entry_editable = None  # Variable para widget Entry temporal

    def editar_cantidad(event):
        nonlocal entry_editable

        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        col = tree.identify_column(event.x)  # e.g. "#5" es columna "Cantidad"
        row = tree.identify_row(event.y)

        if col != "#5":  # Solo editable en columna "Cantidad"
            return

        x, y, width, height = tree.bbox(row, col)
        valor_actual = tree.set(row, "Cantidad")

        if entry_editable:
            entry_editable.destroy()
        entry_editable = tk.Entry(tree, width=10)
        entry_editable.place(x=x, y=y, width=width, height=height)
        entry_editable.insert(0, valor_actual)
        entry_editable.focus()

        def guardar_cambio(event=None):
            nonlocal entry_editable
            nuevo_valor = entry_editable.get()
            try:
                nuevo_valor_num = int(nuevo_valor)
                if nuevo_valor_num < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Ingrese un número entero válido para Cantidad")
                entry_editable.focus()
                return

            tree.set(row, "Cantidad", nuevo_valor_num)

            precio_unitario = float(tree.set(row, "Precio Unitario"))
            total = nuevo_valor_num * precio_unitario
            tree.set(row, "Total", total)

            partidas_detectadas[row]["cantidad"] = nuevo_valor_num

            entry_editable.destroy()
            entry_editable = None

        entry_editable.bind("<Return>", guardar_cambio)
        entry_editable.bind("<FocusOut>", guardar_cambio)

    tree.bind("<Double-1>", editar_cantidad)

    def eliminar_item(partida):
        if messagebox.askyesno("Eliminar", f"¿Deseas eliminar la partida {partida}?"):
            partidas_detectadas.pop(partida, None)
            for item in tree.get_children():
                if tree.item(item)['values'][0] == partida:
                    tree.delete(item)

    def mostrar_detalle(event):
        selected = tree.selection()
        if selected:
            item = selected[0]
            datos = partidas_detectadas[item]
            detalle = tk.Toplevel(ventana_resultados)
            detalle.title(f"Detalle de Partida {item}")
            detalle.geometry("600x500")
            detalle.minsize(400, 300)
            detalle.configure(bg="#ffffff")
            detalle.columnconfigure(0, weight=1)
            detalle.rowconfigure(0, weight=1)

            canvas_detalle = tk.Canvas(detalle, bg="#ffffff", highlightthickness=0)
            canvas_detalle.grid(row=0, column=0, sticky="nsew")

            scrollbar_detalle_v = ttk.Scrollbar(detalle, orient="vertical", command=canvas_detalle.yview)
            scrollbar_detalle_v.grid(row=0, column=1, sticky="ns")

            scrollbar_detalle_h = ttk.Scrollbar(detalle, orient="horizontal", command=canvas_detalle.xview)
            scrollbar_detalle_h.grid(row=1, column=0, sticky="ew")

            canvas_detalle.configure(yscrollcommand=scrollbar_detalle_v.set, xscrollcommand=scrollbar_detalle_h.set)

            frame_detalle = tk.Frame(canvas_detalle, bg="#ffffff")
            canvas_detalle.create_window((0,0), window=frame_detalle, anchor="nw")

            def on_frame_detalle_configure(event):
                canvas_detalle.configure(scrollregion=canvas_detalle.bbox("all"))
            frame_detalle.bind("<Configure>", on_frame_detalle_configure)

            info = (
                f"Partida: {item}\n\n"
                f"Descripción:\n{datos['descripcion']}\n\n"
                f"Unidad de Medida: {datos['unidad_medida']}\n"
                f"Precio Unitario: {datos['precio_unitario']}\n"
                f"Cantidad: {datos['cantidad']}\n"
                f"Total: {datos['cantidad'] * datos['precio_unitario']}\n"
                f"Similitud: {datos['similitud']}%\n"
                f"Palabra Detectada: \"{datos['palabra_coincidente']}\"\n\n"
                f"Comentario Evaluado:\n{datos.get('texto_evaluado', '')}"
            )
            label = tk.Label(frame_detalle, text=info, justify="left", font=("Segoe UI", 10),
                             bg="#ffffff", anchor="w")
            label.pack(padx=20, pady=20, fill="both", expand=True)

    tree.bind("<Double-3>", mostrar_detalle)

    for partida, datos in partidas_detectadas.items():
        total = datos["cantidad"] * datos["precio_unitario"]
        similitud = datos["similitud"]
        tag = "verde" if similitud >= 100 else "naranja" if similitud >= 80 else "amarillo"
        tree.insert("", "end", iid=partida, values=(
            partida,
            datos["descripcion"],
            datos["unidad_medida"],
            datos["precio_unitario"],
            datos["cantidad"],
            total,
            similitud,
            datos["palabra_coincidente"],
            datos.get("texto_evaluado", "")
        ), tags=(tag,))

    label_instruccion = tk.Label(ventana_resultados,
                                 text="Doble clic sobre la celda 'Cantidad' para editarla",
                                 font=("Segoe UI", 9, "italic"), bg="#f9f9f9", fg="#555")
    label_instruccion.grid(row=1, column=0, pady=(5, 10), sticky="w", padx=15)

    btns = tk.Frame(ventana_resultados, bg="#f9f9f9")
    btns.grid(row=2, column=0, pady=10)

    btn_eliminar = tk.Button(btns, text="Eliminar Seleccionados",
                             command=lambda: [
                                 eliminar_item(tree.item(i)['values'][0])
                                 for i in tree.selection()
                                 if tree.item(i)['values'][0] in partidas_detectadas
                                    and partidas_detectadas[tree.item(i)['values'][0]]["similitud"] < 100
                             ],
                             font=("Segoe UI", 10), bg="#d9534f", fg="white",
                             relief="flat", padx=10, pady=4)
    btn_eliminar.grid(row=0, column=0, padx=10)

    btn_exportar = tk.Button(btns, text="Exportar a Excel",
                             command=lambda: exportar_a_excel(partidas_detectadas),
                             font=("Segoe UI", 10), bg="#5cb85c", fg="white",
                             relief="flat", padx=10, pady=4)
    btn_exportar.grid(row=0, column=1, padx=10)

def iniciar_proceso(api_url, contrato_info):
    """
    Realiza la validación de partidas solicitando un archivo Excel, 
    obteniendo los datos de la API, y aplicando el proceso de matching.
    
    Se recibe además un diccionario 'contrato_info' con la información
    adicional proporcionada para el contrato, la cual se guardará en cada registro.
    """
    response = requests.get(api_url)
    if response.status_code != 200:
        messagebox.showerror("Error", "Error al obtener los datos de la API")
        return

    file_path = filedialog.askopenfilename(
        title="Seleccionar archivo de Excel", 
        filetypes=[("Excel files", "*.xlsx")]
    )
    if not file_path:
        messagebox.showerror("Error", "No se seleccionó ningún archivo")
        return

    df_excel = pd.read_excel(file_path)
    df_excel.rename(columns={
        "Palabra Relacionada": "palabra",
        "Partida": "partida",
        "Descripción": "descripcion",
        "Unidad de Medida": "unidad_medida",
        "Precio Unitario (USD)": "precio_unitario",
        "Etapa": "etapa",
        "Comments": "comments"
    }, inplace=True)

    api_data = response.json()
    # Normalizamos las palabras de la API usando la función normalizar_texto
    for item in api_data:
        item["palabras_limpias"] = {
            normalizar_texto(p.strip()) 
            for p in item.get("palabra", "").lower().split(",") if p.strip()
        }

    partidas_detectadas = {}

    # Procesamos cada fila del Excel
    for _, row in df_excel.iterrows():
      comment = normalizar_texto(row.get("comments", ""))
    for item in api_data:
        for palabra in item["palabras_limpias"]:
            palabra_encontrada = ''
            match = re.search(rf'\b{re.escape(palabra)}\b', comment)
            if match:
                similitud = 100
                palabra_encontrada = match.group()
            else:
                similitud = mejor_fuzzy_score(palabra, comment)
                if similitud < 60:
                    continue

                palabras_en_comentario = comment.split()
                palabras_validas = [w for w in palabras_en_comentario if len(w) >= 3]
                candidatas = [w for w in palabras_validas if palabra in w]

                if candidatas:
                    mejor_match = max(candidatas, key=lambda w: mejor_fuzzy_score(palabra, w))
                elif palabras_validas:
                    mejor_match = max(palabras_validas, key=lambda w: mejor_fuzzy_score(palabra, w))
                else:
                    mejor_match = max(palabras_en_comentario, key=lambda w: mejor_fuzzy_score(palabra, w))
                palabra_encontrada = mejor_match

            # Guardar o actualizar partidas_detectadas
            partida = item["partida"]
            if partida not in partidas_detectadas:
                partidas_detectadas[partida] = {
                    "descripcion": item["descripcion"],
                    "unidad_medida": item["unidadMedida"],
                    "precio_unitario": item["precioUnitario"],
                    "cantidad": 1,
                    "similitud": similitud,
                    "palabra_coincidente": palabra_encontrada,
                    "texto_evaluado": comment,
                    "contrato_info": str(contrato_info)
                }
            else:
                partidas_detectadas[partida]["cantidad"] += 1
                if similitud > partidas_detectadas[partida]["similitud"]:
                    partidas_detectadas[partida]["similitud"] = similitud
                    partidas_detectadas[partida]["palabra_coincidente"] = palabra_encontrada
                    partidas_detectadas[partida]["texto_evaluado"] = comment

    for item in api_data:
        for palabra in item["palabras_limpias"]:
            palabra_encontrada = ''
            # Buscar coincidencia exacta en el comentario
            match = re.search(rf'\b{re.escape(palabra)}\b', comment)
            if match:
                similitud = 100
                palabra_encontrada = match.group()  # palabra realmente detectada
            else:
                similitud = mejor_fuzzy_score(palabra, comment)
                if similitud >= 60:
                    palabras_en_comentario = comment.split()
                    # Mejor palabra detectada según fuzzy matching
                    mejor_match = max(
                        palabras_en_comentario,
                        key=lambda w: mejor_fuzzy_score(palabra, w)
                    )
                    palabra_encontrada = mejor_match
                else:
                    continue

            if similitud >= 60:
                partida = item["partida"]
                if partida not in partidas_detectadas:
                    partidas_detectadas[partida] = {
                        "descripcion": item["descripcion"],
                        "unidad_medida": item["unidadMedida"],
                        "precio_unitario": item["precioUnitario"],
                        "cantidad": 1,
                        "similitud": similitud,
                        "palabra_coincidente": palabra_encontrada,  # palabra detectada guardada
                        "texto_evaluado": comment,
                        "contrato_info": str(contrato_info)
                    }
                else:
                    partidas_detectadas[partida]["cantidad"] += 1
                    # Actualizar sólo si similitud mejora
                    if similitud > partidas_detectadas[partida]["similitud"]:
                        partidas_detectadas[partida]["similitud"] = similitud
                        partidas_detectadas[partida]["palabra_coincidente"] = palabra_encontrada
                        partidas_detectadas[partida]["texto_evaluado"] = comment
        comment = normalizar_texto(row.get("comments", ""))
      
      
        for item in api_data:
            for palabra in item["palabras_limpias"]:
                palabra_encontrada = ''
                # Se busca coincidencia exacta con límite de palabra
                match = re.search(rf'\b{re.escape(palabra)}\b', comment)
                if match:
                    similitud = 100
                    palabra_encontrada = match.group()
                else:
                    similitud = mejor_fuzzy_score(palabra, comment)
                    if similitud >= 60:
                        # Seleccionamos la palabra en el comentario con mayor similitud
                        palabras_en_comentario = comment.split()
                        mejor_match = max(palabras_en_comentario, 
                                          key=lambda w: mejor_fuzzy_score(palabra, w))
                        palabra_encontrada = mejor_match
                    else:
                        continue  # No cumple el umbral

                if similitud >= 60:
                    partida = item["partida"]
                    if partida not in partidas_detectadas:
                        partidas_detectadas[partida] = {
                            "descripcion": item["descripcion"],
                            "unidad_medida": item["unidadMedida"],
                            "precio_unitario": item["precioUnitario"],
                            "cantidad": 1,
                            "similitud": similitud,
                            "palabra_coincidente": palabra_encontrada,
                            "texto_evaluado": comment,
                            "contrato_info": str(contrato_info)  # Se guarda esta info si la necesitas para otro fin
                        }
                    else:
                        partidas_detectadas[partida]["cantidad"] += 1
                        if similitud > partidas_detectadas[partida]["similitud"]:
                            partidas_detectadas[partida]["similitud"] = similitud
                            partidas_detectadas[partida]["palabra_coincidente"] = palabra_encontrada
                            partidas_detectadas[partida]["texto_evaluado"] = comment

    if partidas_detectadas:
        mostrar_resultados(partidas_detectadas)
    else:
        messagebox.showinfo("Validación Completada", "No se encontraron coincidencias en los comentarios.")

# =============================================================================
# INTERFAZ GRÁFICA: INFORMACIÓN ADICIONAL POR CONTRATO
# =============================================================================

def iniciar_analisis_contratoA():
    """
    Captura la información ingresada en el formulario de Contrato A, 
    y luego invoca el proceso de validación utilizando la URL correspondiente.
    """
    info = {
        "Agujero": entryA_agujero.get(),
        "Diámetro Barrena": entryA_diam_barrena.get(),
        "Temperatura Fondo": entryA_temp_fondo.get(),
        "Tipo de Lodo": entryA_tipo_lodo.get(),
        "Densidad de Lodo": entryA_dens_lodo.get(),
        "Aditivos Lodo": entryA_aditivos_lodo.get(),
        "Densidad Lechada Amarre": entryA_dens_amarre.get(),
        "Densidad Lechada Línea": entryA_dens_linea.get(),
        "Aditivos Cemento": entryA_aditivos_cem.get(),
        "Diámetro TR": entryA_diam_tr.get(),
        "Tornillo": entryA_tornillo.get(),
        "Temblorina": entryA_temblorina.get(),
        "Limpia Lodo": entryA_limpia_lodo.get(),
        "Centrífuga Decantadora": entryA_centrifuga.get(),
        "Recolección y Transporte de Recortes": entryA_recortes.get()
    }
    # URL para Contrato A (puedes cambiarla según corresponda)
    api_url = "https://python.apiigrtec.site/api/PalabrasRelacionadas"
    iniciar_proceso(api_url, info)

def iniciar_analisis_contratoB():
    """
    Captura la información ingresada en el formulario de Contrato B, 
    y luego invoca el proceso de validación utilizando la URL correspondiente.
    """
    info = {
        "Agujero": entryB_agujero.get(),
        "Diámetro Barrena": entryB_diam_barrena.get(),
        "Temperatura Fondo": entryB_temp_fondo.get(),
        "Tipo de Lodo": entryB_tipo_lodo.get(),
        "Densidad de Lodo": entryB_dens_lodo.get(),
        "Aditivos Lodo": entryB_aditivos_lodo.get(),
        "Densidad Lechada Amarre": entryB_dens_amarre.get(),
        "Densidad Lechada Línea": entryB_dens_linea.get(),
        "Aditivos Cemento": entryB_aditivos_cem.get(),
        "Diámetro TR": entryB_diam_tr.get(),
        "Tornillo": entryB_tornillo.get(),
        "Temblorina": entryB_temblorina.get(),
        "Limpia Lodo": entryB_limpia_lodo.get(),
        "Centrífuga Decantadora": entryB_centrifuga.get(),
        "Recolección y Transporte de Recortes": entryB_recortes.get()
    }
    # URL para Contrato B (puedes cambiarla según corresponda)
    api_url = "https://python.apiigrtec.site/api/PalabrasRelacionadas/GetPalabrasRelacionadas1"
    iniciar_proceso(api_url, info)
# =============================================================================
# VENTANA PRINCIPAL Y NOTEBOOK
# =============================================================================

root = tk.Tk()
root.title("Validador de Partidas y Datos de Contrato")
root.geometry("900x700")
root.minsize(700, 500)
root.configure(bg="#f4f6f8")

# Configurar la grilla para que el frame principal se expanda
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

# Frame principal que contendrá el canvas y scrollbars
main_frame = tk.Frame(root)
main_frame.grid(row=0, column=0, sticky="nsew")
main_frame.columnconfigure(0, weight=1)
main_frame.rowconfigure(0, weight=1)

# Canvas para scroll
canvas_root = tk.Canvas(main_frame, bg="#f4f6f8", highlightthickness=0)
canvas_root.grid(row=0, column=0, sticky="nsew")

# Barras de scroll vertical y horizontal
scrollbar_root_v = ttk.Scrollbar(main_frame, orient="vertical", command=canvas_root.yview)
scrollbar_root_v.grid(row=0, column=1, sticky="ns")

scrollbar_root_h = ttk.Scrollbar(main_frame, orient="horizontal", command=canvas_root.xview)
scrollbar_root_h.grid(row=1, column=0, sticky="ew")

canvas_root.configure(yscrollcommand=scrollbar_root_v.set, xscrollcommand=scrollbar_root_h.set)

# Frame interior donde irá el notebook
frame_interior_root = tk.Frame(canvas_root, bg="#f4f6f8")
canvas_root.create_window((0, 0), window=frame_interior_root, anchor="nw")

def on_frame_configure_root(event):
    canvas_root.configure(scrollregion=canvas_root.bbox("all"))
frame_interior_root.bind("<Configure>", on_frame_configure_root)

# Ahora creamos el notebook como hijo del frame interior (scrollable)
notebook = ttk.Notebook(frame_interior_root)
notebook.pack(expand=True, fill="both", padx=10, pady=10)

# ----- Pestaña Contrato A -----
pestaña_A = ttk.Frame(notebook)
notebook.add(pestaña_A, text="Contrato A")

# Información General para Contrato A
frame_infoA = ttk.LabelFrame(pestaña_A, text="Información General")
frame_infoA.pack(fill="both", expand=True, padx=5, pady=5)
frame_infoA.columnconfigure(1, weight=1)

tk.Label(frame_infoA, text="Agujero:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryA_agujero = tk.Entry(frame_infoA)
entryA_agujero.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_infoA, text="Diámetro de Barrena:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryA_diam_barrena = tk.Entry(frame_infoA)
entryA_diam_barrena.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_infoA, text="Temperatura de Fondo:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryA_temp_fondo = tk.Entry(frame_infoA)
entryA_temp_fondo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

# LODO para Contrato A
frame_lodoA = ttk.LabelFrame(pestaña_A, text="Lodo")
frame_lodoA.pack(fill="both", expand=True, padx=5, pady=5)
frame_lodoA.columnconfigure(1, weight=1)

tk.Label(frame_lodoA, text="Tipo de Lodo:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryA_tipo_lodo = tk.Entry(frame_lodoA)
entryA_tipo_lodo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_lodoA, text="Densidad de Lodo:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryA_dens_lodo = tk.Entry(frame_lodoA)
entryA_dens_lodo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_lodoA, text="Aditivos:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryA_aditivos_lodo = tk.Entry(frame_lodoA)
entryA_aditivos_lodo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

# CEMENTO para Contrato A
frame_cemA = ttk.LabelFrame(pestaña_A, text="Cemento")
frame_cemA.pack(fill="both", expand=True, padx=5, pady=5)
frame_cemA.columnconfigure(1, weight=1)

tk.Label(frame_cemA, text="Densidad Lechada de Amarre:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryA_dens_amarre = tk.Entry(frame_cemA)
entryA_dens_amarre.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_cemA, text="Densidad Lechada de Línea:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryA_dens_linea = tk.Entry(frame_cemA)
entryA_dens_linea.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_cemA, text="Aditivos:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryA_aditivos_cem = tk.Entry(frame_cemA)
entryA_aditivos_cem.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

# TR para Contrato A
frame_trA = ttk.LabelFrame(pestaña_A, text="TR")
frame_trA.pack(fill="both", expand=True, padx=5, pady=5)
frame_trA.columnconfigure(1, weight=1)

tk.Label(frame_trA, text="Diámetro TR (ej. 20, 13 3/8, 9 5/8, etc.):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryA_diam_tr = tk.Entry(frame_trA)
entryA_diam_tr.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

# Equipo de Control de Sólidos para Contrato A
frame_solidosA = ttk.LabelFrame(pestaña_A, text="Equipo de Control de Sólidos")
frame_solidosA.pack(fill="both", expand=True, padx=5, pady=5)
frame_solidosA.columnconfigure(1, weight=1)

tk.Label(frame_solidosA, text="Tornillo:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryA_tornillo = tk.Entry(frame_solidosA)
entryA_tornillo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_solidosA, text="Temblorina:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryA_temblorina = tk.Entry(frame_solidosA)
entryA_temblorina.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_solidosA, text="Limpia Lodo:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryA_limpia_lodo = tk.Entry(frame_solidosA)
entryA_limpia_lodo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_solidosA, text="Centrífuga Decantadora:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
entryA_centrifuga = tk.Entry(frame_solidosA)
entryA_centrifuga.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

# Servicios Adicionales para Contrato A
frame_serviciosA = ttk.LabelFrame(pestaña_A, text="Servicios Adicionales")
frame_serviciosA.pack(fill="both", expand=True, padx=5, pady=5)
frame_serviciosA.columnconfigure(1, weight=1)

tk.Label(frame_serviciosA, text="Recolección y Transporte de Recortes:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryA_recortes = tk.Entry(frame_serviciosA)
entryA_recortes.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

btn_iniciarA = tk.Button(pestaña_A, text="Cargar Archivo y Analizar (Contrato A)", 
                         bg="#4a90e2", fg="white", command=iniciar_analisis_contratoA)
btn_iniciarA.pack(pady=10)

# ----- Pestaña Contrato B -----
pestaña_B = ttk.Frame(notebook)
notebook.add(pestaña_B, text="Contrato B")

# Información General para Contrato B
frame_infoB = ttk.LabelFrame(pestaña_B, text="Información General")
frame_infoB.pack(fill="both", expand=True, padx=5, pady=5)
frame_infoB.columnconfigure(1, weight=1)

tk.Label(frame_infoB, text="Agujero:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryB_agujero = tk.Entry(frame_infoB)
entryB_agujero.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_infoB, text="Diámetro de Barrena:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryB_diam_barrena = tk.Entry(frame_infoB)
entryB_diam_barrena.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_infoB, text="Temperatura de Fondo:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryB_temp_fondo = tk.Entry(frame_infoB)
entryB_temp_fondo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

# LODO para Contrato B
frame_lodoB = ttk.LabelFrame(pestaña_B, text="Lodo")
frame_lodoB.pack(fill="both", expand=True, padx=5, pady=5)
frame_lodoB.columnconfigure(1, weight=1)

tk.Label(frame_lodoB, text="Tipo de Lodo:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryB_tipo_lodo = tk.Entry(frame_lodoB)
entryB_tipo_lodo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_lodoB, text="Densidad de Lodo:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryB_dens_lodo = tk.Entry(frame_lodoB)
entryB_dens_lodo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_lodoB, text="Aditivos:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryB_aditivos_lodo = tk.Entry(frame_lodoB)
entryB_aditivos_lodo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

# CEMENTO para Contrato B
frame_cemB = ttk.LabelFrame(pestaña_B, text="Cemento")
frame_cemB.pack(fill="both", expand=True, padx=5, pady=5)
frame_cemB.columnconfigure(1, weight=1)

tk.Label(frame_cemB, text="Densidad Lechada de Amarre:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryB_dens_amarre = tk.Entry(frame_cemB)
entryB_dens_amarre.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_cemB, text="Densidad Lechada de Línea:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryB_dens_linea = tk.Entry(frame_cemB)
entryB_dens_linea.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_cemB, text="Aditivos:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryB_aditivos_cem = tk.Entry(frame_cemB)
entryB_aditivos_cem.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

# TR para Contrato B
frame_trB = ttk.LabelFrame(pestaña_B, text="TR")
frame_trB.pack(fill="both", expand=True, padx=5, pady=5)
frame_trB.columnconfigure(1, weight=1)

tk.Label(frame_trB, text="Diámetro TR (ej. 20, 13 3/8, 9 5/8, etc.):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryB_diam_tr = tk.Entry(frame_trB)
entryB_diam_tr.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

# Equipo de Control de Sólidos para Contrato B
frame_solidosB = ttk.LabelFrame(pestaña_B, text="Equipo de Control de Sólidos")
frame_solidosB.pack(fill="both", expand=True, padx=5, pady=5)
frame_solidosB.columnconfigure(1, weight=1)

tk.Label(frame_solidosB, text="Tornillo:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryB_tornillo = tk.Entry(frame_solidosB)
entryB_tornillo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_solidosB, text="Temblorina:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entryB_temblorina = tk.Entry(frame_solidosB)
entryB_temblorina.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_solidosB, text="Limpia Lodo:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entryB_limpia_lodo = tk.Entry(frame_solidosB)
entryB_limpia_lodo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

tk.Label(frame_solidosB, text="Centrífuga Decantadora:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
entryB_centrifuga = tk.Entry(frame_solidosB)
entryB_centrifuga.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

# Servicios Adicionales para Contrato B
frame_serviciosB = ttk.LabelFrame(pestaña_B, text="Servicios Adicionales")
frame_serviciosB.pack(fill="both", expand=True, padx=5, pady=5)
frame_serviciosB.columnconfigure(1, weight=1)

tk.Label(frame_serviciosB, text="Recolección y Transporte de Recortes:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entryB_recortes = tk.Entry(frame_serviciosB)
entryB_recortes.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

btn_iniciarB = tk.Button(pestaña_B, text="Cargar Archivo y Analizar (Contrato B)", 
                         bg="#4a90e2", fg="white", command=iniciar_analisis_contratoB)
btn_iniciarB.pack(pady=10)

root.mainloop()

