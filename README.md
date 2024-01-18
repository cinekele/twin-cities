# Twin Cities

...

## Installation

This project uses Docker for easy setup and execution. To install, follow these steps:

1. Install Docker on your machine if you haven't already.
2. Clone this repository.
3. Navigate to the project directory.

```sh
docker build -t your-image-name .
```

## Usage

Two environment variables are required to run this docker - USER and PASSWORD to wikidata (you can set them using --env-file or --env (-e) flags).
To run this project, use the following command:

```sh
docker run -p 8050:8050 -e USER wikidata-username -e PASSWORD wikidata-password your-image-name
```

The application will be available at `http://localhost:8050`.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
