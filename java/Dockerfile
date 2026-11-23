FROM maven:3.9-eclipse-temurin-21
WORKDIR /app
COPY pom.xml .
RUN mvn -q dependency:copy-dependencies -DoutputDirectory=lib
COPY src ./src
RUN mkdir -p out && javac -cp "lib/*" -d out $(find src -name '*.java')
CMD ["java", "-cp", "out:lib/*", "app.Main"]
