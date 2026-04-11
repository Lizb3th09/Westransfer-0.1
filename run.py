if __name__ == '__main__':
    print("🚀 Iniciando WeTransfer Clone...")
    
    from app import app
    app.run(debug=False, host='0.0.0.0', port=5000) 