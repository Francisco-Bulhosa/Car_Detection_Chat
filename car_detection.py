import tensorflow as tf
#LLAMA 2
image = tf.keras.preprocessing.image.load_img('car.jpg', target_size=(224, 224))
input_array = tf.keras.preprocessing.image.img_to_array(image)
input_array = tf.expand_dims(input_array, 0)  # Create a batch
normalized_input = input_array / 255.0  # Normalize to [0,1] 




# Define the model architecture
model_architecture = [
tf.keras.layers.Conv2D(32, (3, 3), activation='relu', input_shape=(224, 224, 3)),
tf.keras.layers.MaxPooling2D((2, 2)),
tf.keras.layers.Flatten(),
tf.keras.layers.Dense(128, activation='relu'),
tf.keras.layers.Dense(10, activation='softmax')
]
# Create the model
model = tf.keras.Sequential(model_architecture)
# Compile the model
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
# Train the model
model.fit(x_train, y_train, epochs=10, batch_size=32, validation_data=(x_val, y_val))
# Evaluate the model
loss, accuracy = model.evaluate(x_test, y_test)
print('Test loss:', loss)
print('Test accuracy:', accuracy)