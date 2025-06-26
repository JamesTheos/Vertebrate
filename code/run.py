from app import create_app, create_topics_if_not_exist, consume_messages, data_store, Kafkaserver
import threading
flask_app = create_app()

if __name__ == "__main__":
    create_topics_if_not_exist(Kafkaserver, data_store.keys())
    
    flask_app.run(debug=True, use_reloader=False,port=5001)
    threading.Thread(target=consume_messages, daemon=True).start()
